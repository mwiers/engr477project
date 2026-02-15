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
    - Mass flow is not solved from choking; instead, we use the passed-in m_dot (cycle deck assumption).
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

        # Choking check based on critical pressure at M=1
        p_star = Pt * critical_pressure_ratio(gamma)
        choked = p_ambient <= p_star * 1.0001

        if choked:
            # If nozzle is CD, attempt supersonic branch for A_e/A_t > 1
            if abs(area_ratio - 1.0) < 1e-6:
                Me = 1.0
            else:
                try:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=True)
                except Exception:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=False)
        else:
            # Not choked: match exit static pressure to ambient
            pe = p_ambient

            def f(M):
                return pe - static_pressure_from_Pt(Pt, gamma, M)

            lo, hi = 1e-9, 0.999
            flo, fhi = f(lo), f(hi)
            if flo * fhi > 0:
                Me = 0.3
            else:
                for _ in range(80):
                    mid = 0.5 * (lo + hi)
                    fmid = f(mid)
                    if abs(fmid) < 1e-6:
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
        V_is = Me * a

        # Nozzle efficiency applied as kinetic energy efficiency
        V = math.sqrt(max(self.eta, 0.0)) * V_is

        mdot = inlet.m_dot
        F_gross = mdot * V + (pe - p_ambient) * Ae

        return {
            "Pt": Pt,
            "Tt": Tt,
            "Me": Me,
            "Te": Te_is,
            "pe": pe,
            "V": V,
            "At": At,
            "Ae": Ae,
            "choked": bool(choked),
            "F_gross": float(F_gross),
        }
