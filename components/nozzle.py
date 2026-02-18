from __future__ import annotations

import math
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState
from utils import (
    area_from_diameter,
    critical_pressure_ratio,
    solve_mach_from_area_ratio,
    static_pressure_from_Pt,
    static_temperature_from_Tt,
)


def choked_mass_flow(Pt: float, Tt: float, At: float, gamma: float, R: float) -> float:
    """Ideal-gas choked mass flow rate through the throat (M=1).

    mdot = Pt * At / sqrt(Tt) * sqrt(gamma/R) * (2/(gamma+1))^((gamma+1)/(2(gamma-1)))

    Notes:
    - Use total conditions *at the nozzle* (after any inlet pr losses).
    - No discharge coefficient is applied (Cd = 1).
    """
    if At <= 0.0 or Pt <= 0.0 or Tt <= 0.0:
        return 0.0

    term = (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
    return Pt * At / math.sqrt(Tt) * math.sqrt(gamma / R) * term


@dataclass
class Nozzle(Component):
    """
    Converging or converging-diverging nozzle (cycle deck style).

    Inputs:
    - eta: nozzle kinetic-energy efficiency (V^2 = eta * V_is^2)
    - pr: total-pressure loss before nozzle expansion (Pt_noz = pr * Pt_in)
    - throat_d, exit_d: geometric constraints used to infer exit Mach if choked

    Assumptions:
    - Quasi-1D isentropic relations used for Pt/Tt -> p/T at a given Mach, with gamma(Tt) evaluated at inlet.
    - If choked, solve exit Mach from A_e/A_t (A_t assumed to be A*).
    - If not choked, set p_e = p_ambient and solve for Mach from Pt/p.
    - Mass flow is normally the passed-in inlet.m_dot, but when choked we also report the nozzle
      capacity (mdot_choked) so the engine can optionally iterate to match it.
    """
    eta: float
    pr: float
    throat_d: float
    exit_d: float

    def process(self, inlet: FluidState, p_ambient: float) -> dict:
        """
        Process the flow through the nozzle, returning a dictionary of relevant output properties.
        """
        Pt = inlet.Pt * self.pr
        Tt = inlet.Tt

        gamma = inlet.model.gamma(Tt)
        R = inlet.model.R

        At = area_from_diameter(self.throat_d)
        Ae = area_from_diameter(self.exit_d)
        area_ratio = Ae / At if At > 0 else 1.0

        # --- Back-pressure guard ---
        if Pt <= p_ambient * 1.000001:
            Me = 0.0
            Te = Tt
            pe = p_ambient
            ue = 0.0
            F_gross = (pe - p_ambient) * Ae  # = 0
            return {
                "Pt": Pt,
                "Tt": Tt,
                "Me": Me,
                "Te": Te,
                "pe": pe,
                "ue": ue,
                "At": At,
                "Ae": Ae,
                "choked": False,
                "mdot_choked": 0.0,
                "F_gross": float(F_gross),
                "note": "Pt<=p_ambient: no forward-flow nozzle solution; clamped.",
            }

        # Choking check based on critical pressure at M=1
        p_star = Pt * critical_pressure_ratio(gamma)
        choked = p_ambient <= p_star * 1.01

        if choked:
            if abs(area_ratio - 1.0) < 1e-6:
                Me = 1.0
            else:
                try:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=True)
                except Exception:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=False)
        else:
            pe = p_ambient

            def f(M):
                return pe - static_pressure_from_Pt(Pt, gamma, M)

            # Robust bracketing scan
            Ms = [1e-6 + (0.999 - 1e-6) * i / 200 for i in range(201)]
            fs = [f(M) for M in Ms]
            bracket = None
            for i in range(1, len(Ms)):
                if fs[i - 1] * fs[i] <= 0:
                    bracket = (Ms[i - 1], Ms[i], fs[i - 1], fs[i])
                    break

            if bracket is None:
                raise ValueError(
                    "Nozzle unchoked solve could not bracket Me in (0,1). "
                    f"Pt={Pt:.3e}, gamma={gamma:.4f}, p_amb={p_ambient:.3e}"
                    f", p*={p_star:.3e}, choked={choked}"
                )

            lo, hi, flo, fhi = bracket
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                fmid = f(mid)
                if abs(fmid) < 1e-8:
                    break
                if flo * fmid <= 0:
                    hi, fhi = mid, fmid
                else:
                    lo, flo = mid, fmid
            Me = 0.5 * (lo + hi)

        # Exit static properties (isentropic relations)
        Te_is = static_temperature_from_Tt(Tt, gamma, Me)
        pe = static_pressure_from_Pt(Pt, gamma, Me)

        a = math.sqrt(gamma * R * Te_is)
        u_is = Me * a

        # Nozzle efficiency applied as kinetic energy efficiency
        ue = math.sqrt(max(self.eta, 0.0)) * u_is

        mdot = inlet.m_dot
        F_gross = mdot * ue + (pe - p_ambient) * Ae

        mdot_star = choked_mass_flow(Pt, Tt, At, gamma, R) if choked else 0.0

        return {
            "Pt": Pt,
            "Tt": Tt,
            "Me": Me,
            "Te": Te_is,
            "pe": pe,
            "ue": ue,
            "At": At,
            "Ae": Ae,
            "choked": bool(choked),
            "mdot_choked": float(mdot_star),
            "F_gross": float(F_gross),
        }
