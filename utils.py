from __future__ import annotations

import math
from dataclasses import dataclass

R_UNIVERSAL = 8_314.46261815324  # J/(kmol*K)

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def is_close(a: float, b: float, rel: float = 1e-9, abs_: float = 0.0) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))

def area_from_diameter(d: float) -> float:
    return math.pi * (d**2) / 4.0

def diameter_from_area(a: float) -> float:
    return math.sqrt(4.0 * a / math.pi)

def stagnation_temperature(T: float, gamma: float, M: float) -> float:
    return T * (1.0 + (gamma - 1.0) / 2.0 * M**2)

def stagnation_pressure(p: float, gamma: float, M: float) -> float:
    return p * (1.0 + (gamma - 1.0) / 2.0 * M**2) ** (gamma / (gamma - 1.0))

def static_temperature_from_Tt(Tt: float, gamma: float, M: float) -> float:
    return Tt / (1.0 + (gamma - 1.0) / 2.0 * M**2)

def static_pressure_from_Pt(Pt: float, gamma: float, M: float) -> float:
    return Pt / (1.0 + (gamma - 1.0) / 2.0 * M**2) ** (gamma / (gamma - 1.0))

def critical_pressure_ratio(gamma: float) -> float:
    """p*/Pt for M=1 (critical pressure ratio)."""
    return (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))

def area_mach_relation(M: float, gamma: float) -> float:
    """Return A/A* for given Mach and gamma (isentropic)."""
    if M <= 0:
        raise ValueError("Mach must be > 0")
    term1 = 2.0 / (gamma + 1.0)
    term2 = 1.0 + (gamma - 1.0) / 2.0 * M**2
    exponent = (gamma + 1.0) / (2.0 * (gamma - 1.0))
    return (1.0 / M) * (term1 * term2) ** exponent

def solve_mach_from_area_ratio(area_ratio: float, gamma: float, supersonic: bool) -> float:
    """Solve isentropic A/A* = area_ratio for M (subsonic or supersonic branch)."""
    if area_ratio < 1.0:
        raise ValueError("Area ratio must be >= 1")
    # Bracket
    if supersonic:
        lo, hi = 1.0 + 1e-9, 20.0
    else:
        lo, hi = 1e-9, 1.0 - 1e-9

    def f(M):
        return area_mach_relation(M, gamma) - area_ratio

    # Simple bisection (monotonic on each branch)
    flo, fhi = f(lo), f(hi)
    # Expand if needed (supersonic)
    if supersonic and flo * fhi > 0:
        # increase hi
        for _ in range(40):
            hi *= 1.5
            fhi = f(hi)
            if flo * fhi <= 0:
                break
    if flo * fhi > 0:
        raise RuntimeError("Failed to bracket Mach for area ratio")

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        fmid = f(mid)
        if abs(fmid) < 1e-10:
            return mid
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)
