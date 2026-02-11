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
    eta: float
    pr: float  # Pt_out / Pt_in pressure loss before nozzle (e.g., nozzle duct PR)
    throat_d: float
    exit_d: float

    def process(self, inlet: FluidState, p_ambient: float) -> dict:
        st = inlet.update()
        Pt = st.p0 * self.pr
        Tt = st.T0

        gamma = st.model.gamma(Tt)
        R = st.model.R
        At = area_from_diameter(self.throat_d)
        Ae = area_from_diameter(self.exit_d)
        area_ratio = Ae / At if At > 0 else 1.0

        # Determine choking
        p_star = Pt * critical_pressure_ratio(gamma)
        choked = p_ambient <= p_star * 1.0001  # allow numeric slack

        if choked:
            # Determine exit Mach based on area ratio:
            if abs(area_ratio - 1.0) < 1e-6:
                Me = 1.0
            else:
                # For CD nozzle, choose supersonic branch if possible (Pt/Pa high),
                # otherwise subsonic. We'll attempt supersonic, and fall back to subsonic if it fails.
                try:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=True)
                except Exception:
                    Me = solve_mach_from_area_ratio(area_ratio, gamma, supersonic=False)
        else:
            # Not choked: set exit pressure ~ ambient and solve for Me from isentropic Pt/pe
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

        Te_is = static_temperature_from_Tt(Tt, gamma, Me)
        # Nozzle efficiency applied to kinetic energy: V_actual^2 = eta * V_is^2
        a = math.sqrt(gamma * R * Te_is)
        V_is = Me * a
        V = math.sqrt(max(self.eta, 0.0)) * V_is

        pe = static_pressure_from_Pt(Pt, gamma, Me)
        Te = Te_is  # keep Te for reporting (eff applied to V)

        mdot = st.m_dot
        F_gross = mdot * V + (pe - p_ambient) * Ae

        return {
            "Pt": Pt,
            "Tt": Tt,
            "Me": Me,
            "Te": Te,
            "pe": pe,
            "V": V,
            "At": At,
            "Ae": Ae,
            "choked": bool(choked),
            "F_gross": F_gross,
        }
