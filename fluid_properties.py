from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import math


Composition = Literal["air", "products"]


def _trapz(y: list[float], x: list[float]) -> float:
    s = 0.0
    for i in range(1, len(x)):
        s += 0.5 * (y[i] + y[i - 1]) * (x[i] - x[i - 1])
    return s


@dataclass(frozen=True)
class FluidModel:
    """
    Ideal-gas, calorically-imperfect property model with variable cp(T).

    Key assumptions:
    - Ideal gas equation of state (p = rho R T), constant R.
    - cp is temperature-dependent (either constant or simple polynomial).
    - gamma(T) computed from cp(T) and R: gamma = cp/(cp-R).
    - Enthalpy h(T) computed as integral of cp(T) dT from a reference state.
    - Entropy s(T,p) computed from integral of cp(T)/T dT - R ln(p/p_ref).

    IMPORTANT:
    - This model treats "air" and "products" as different cp(T) curves but does not
      model changing chemical composition, dissociation, or real-gas effects.
    - Entropy is stored as a relative quantity with a chosen (T_ref, p_ref).
    """

    R: float  # J/(kg*K)
    composition: Composition = "air"
    cp_mode: Literal["constant", "poly"] = "poly"
    cp_const: float = 1004.5  # J/(kg*K) if cp_mode="constant"

    # Reference for h and s (absolute reference doesn't matter; only differences matter).
    T_ref: float = 288.15
    p_ref: float = 101325.0

    def cp(self, T: float) -> float:
        """Specific heat at constant pressure cp(T) [J/(kg*K)]."""
        if self.cp_mode == "constant":
            return float(self.cp_const)

        # Lightweight polynomial in (T-300) for cycle work (not NASA polynomials).
        # Valid for "reasonable" gas-turbine temperatures (roughly 200–3000 K).
        x = T - 300.0
        if self.composition == "air":
            a, b, c = 1003.5, 0.100, -1.0e-5
        else:
            a, b, c = 1150.0, 0.120, -1.2e-5
        return float(a + b * x + c * x * x)

    def gamma(self, T: float) -> float:
        """Ratio of specific heats gamma(T)."""
        cp = self.cp(T)
        cv = cp - self.R
        return float(cp / cv)

    # ---------------------------
    # Thermodynamic integrals
    # ---------------------------

    def h(self, T: float, *, n: int = 400) -> float:
        """
        Sensible enthalpy relative to T_ref:
            h(T) - h(T_ref) = ∫_{T_ref}^{T} cp(T) dT

        Uses numerical integration (trapezoidal) for robustness with arbitrary cp(T).
        """
        if T == self.T_ref:
            return 0.0
        T1, T2 = (self.T_ref, T) if T > self.T_ref else (T, self.T_ref)
        xs = [T1 + (T2 - T1) * i / n for i in range(n + 1)]
        ys = [self.cp(x) for x in xs]
        val = _trapz(ys, xs)
        return float(val if T > self.T_ref else -val)

    def s(self, T: float, p: float, *, n: int = 400) -> float:
        """
        Entropy relative to (T_ref, p_ref):
            s(T,p) - s(T_ref,p_ref) = ∫_{T_ref}^{T} cp(T)/T dT - R ln(p/p_ref)

        Uses numerical integration (trapezoidal) for robustness.
        """
        if T == self.T_ref:
            integ = 0.0
        else:
            T1, T2 = (self.T_ref, T) if T > self.T_ref else (T, self.T_ref)
            xs = [T1 + (T2 - T1) * i / n for i in range(n + 1)]
            ys = [self.cp(x) / x for x in xs]
            integ = _trapz(ys, xs)
            if T < self.T_ref:
                integ = -integ

        return float(integ - self.R * math.log(p / self.p_ref))

    # ---------------------------
    # Inversion helpers
    # ---------------------------

    def T_from_h(self, h_target: float, *, T_lo: float = 50.0, T_hi: float = 5000.0) -> float:
        """
        Invert h(T) for T via bisection. h is monotonic for cp>0.

        h_target is enthalpy relative to T_ref (same definition as h()).
        """
        lo, hi = T_lo, T_hi
        hlo, hhi = self.h(lo), self.h(hi)
        if not (hlo <= h_target <= hhi):
            # Expand bounds if necessary
            for _ in range(50):
                if h_target < hlo:
                    hi = lo
                    lo = max(1.0, lo * 0.5)
                elif h_target > hhi:
                    lo = hi
                    hi = hi * 1.5
                hlo, hhi = self.h(lo), self.h(hi)
                if hlo <= h_target <= hhi:
                    break
            else:
                raise ValueError("Failed to bracket T for target enthalpy.")

        for _ in range(80):
            mid = 0.5 * (lo + hi)
            hmid = self.h(mid)
            if abs(hmid - h_target) < 1e-7 * max(1.0, abs(h_target)):
                return float(mid)
            if hmid < h_target:
                lo = mid
            else:
                hi = mid
        return float(0.5 * (lo + hi))

    def T_isentropic_from_p_ratio(
        self,
        T_in: float,
        p_in: float,
        p_out: float,
        *,
        T_lo: float = 50.0,
        T_hi: float = 5000.0,
    ) -> float:
        """
        Solve for T_out such that s(T_out, p_out) = s(T_in, p_in).
        This is the correct 'variable-cp' isentropic temperature change.

        This is used for compressors/fans and turbines to find the isentropic endpoint.
        """
        s_target = self.s(T_in, p_in)

        lo, hi = T_lo, T_hi

        def f(T: float) -> float:
            return self.s(T, p_out) - s_target

        flo, fhi = f(lo), f(hi)
        if flo * fhi > 0:
            # Try to bracket near T_in depending on pressure change direction
            lo = max(1.0, 0.2 * T_in)
            hi = 3.0 * T_in
            flo, fhi = f(lo), f(hi)
            if flo * fhi > 0:
                # As a last resort, expand outward
                lo, hi = 50.0, 8000.0
                flo, fhi = f(lo), f(hi)
                if flo * fhi > 0:
                    raise ValueError("Failed to bracket isentropic temperature solve.")

        for _ in range(90):
            mid = 0.5 * (lo + hi)
            fmid = f(mid)
            if abs(fmid) < 1e-10:
                return float(mid)
            if flo * fmid <= 0:
                hi, fhi = mid, fmid
            else:
                lo, flo = mid, fmid
        return float(0.5 * (lo + hi))


@dataclass
class FluidState:
    """
    Flow state container for cycle analysis.

    This model is primarily a *stagnation (total) property* cycle deck:
    - Internally, engine stations are treated as low Mach (M≈0),
      so static ≈ stagnation.
    - Ambient can carry a freestream Mach and static conditions.

    Stored properties:
    - Stagnation: Tt, Pt
    - Optional static: T, p, M (useful for ambient and nozzle reporting)
    - Derived: cp_t, gamma_t, ht, st (relative to model reference)
    """

    m_dot: float
    model: FluidModel
    composition: Composition = "air"

    # Stagnation (primary for the cycle)
    Tt: float = 288.15
    Pt: float = 101325.0

    # Static (optional; for ambient/nozzle)
    T: Optional[float] = None
    p: Optional[float] = None
    M: float = 0.0

    # Derived (computed in update_thermo)
    cp_t: float = 0.0
    gamma_t: float = 0.0
    ht: float = 0.0  # J/kg relative to model reference
    st: float = 0.0  # J/(kg*K) relative to model reference

    def update_thermo(self) -> "FluidState":
        """Compute cp, gamma, ht, st at stagnation conditions."""
        self.cp_t = self.model.cp(self.Tt)
        self.gamma_t = self.model.gamma(self.Tt)
        self.ht = self.model.h(self.Tt)
        self.st = self.model.s(self.Tt, self.Pt)
        return self

    def set_static_equal_total(self) -> "FluidState":
        """Convenience: for internal stations with M≈0, static ≈ stagnation."""
        self.T = self.Tt
        self.p = self.Pt
        self.M = 0.0
        return self

    def copy_with(self, **kwargs) -> "FluidState":
        d = {
            "m_dot": self.m_dot,
            "model": self.model,
            "composition": self.composition,
            "Tt": self.Tt,
            "Pt": self.Pt,
            "T": self.T,
            "p": self.p,
            "M": self.M,
        }
        d.update(kwargs)
        st = FluidState(**d)
        return st.update_thermo()
