from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

Composition = Literal["air", "products"]

@dataclass(frozen=True)
class FluidModel:
    """Simple calorically-imperfect ideal gas model.

    Notes:
    - cp(T) polynomial is approximate; you can swap for NASA CEA/Cantera later.
    - gamma(T) computed from cp(T) and constant R for the chosen gas.
    """

    R: float  # J/(kg*K)
    composition: Composition = "air"
    cp_mode: Literal["constant", "poly"] = "poly"
    cp_const: float = 1004.5  # J/(kg*K) for air around 300 K

    def cp(self, T: float) -> float:
        if self.cp_mode == "constant":
            return self.cp_const

        # Very lightweight polynomial fits (approximate) for educational cycle work.
        # cp = a + b*T + c*T^2  (J/kg-K), valid roughly 200-3000 K.
        if self.composition == "air":
            a, b, c = 1003.5, 0.100, -1.0e-5
        else:
            # combustion products typically higher cp
            a, b, c = 1150.0, 0.120, -1.2e-5
        return a + b * (T - 300.0) + c * (T - 300.0) ** 2

    def gamma(self, T: float) -> float:
        cp = self.cp(T)
        cv = cp - self.R
        return cp / cv

    def h(self, T: float, T_ref: float = 0.0) -> float:
        """Approximate sensible enthalpy relative to T_ref via integral of cp(T)dT."""
        if self.cp_mode == "constant":
            return self.cp_const * (T - T_ref)

        # Integrate polynomial cp(T) in terms of (T-300):
        # cp = a + b*(T-300) + c*(T-300)^2
        # Let x = T-300. Integral cp dT = a*(T) + b*(x^2)/2 + c*(x^3)/3  (since dx=dT)
        def integral(Tx: float) -> float:
            x = Tx - 300.0
            if self.composition == "air":
                a, b, c = 1003.5, 0.100, -1.0e-5
            else:
                a, b, c = 1150.0, 0.120, -1.2e-5
            return a * (Tx) + b * (x**2) / 2.0 + c * (x**3) / 3.0

        return integral(T) - integral(T_ref)

@dataclass
class FluidState:
    """One-dimensional compressible flow state (static + stagnation).

    Conventions:
    - Use SI units.
    - p, p0 in Pa; T, T0 in K; m_dot in kg/s; h in J/kg (relative).
    """
    m_dot: float
    T: float
    p: float
    M: float
    model: FluidModel
    composition: Composition = "air"

    # Computed / cached fields (filled by .update())
    T0: float | None = None
    p0: float | None = None
    cp: float | None = None
    gamma: float | None = None
    R: float | None = None

    def update(self) -> "FluidState":
        gm = self.model.gamma(self.T)
        cp = self.model.cp(self.T)
        T0 = self.T * (1.0 + (gm - 1.0) / 2.0 * self.M**2)
        p0 = self.p * (1.0 + (gm - 1.0) / 2.0 * self.M**2) ** (gm / (gm - 1.0))
        self.gamma = gm
        self.cp = cp
        self.T0 = T0
        self.p0 = p0
        self.R = self.model.R
        return self

    def copy_with(self, **kwargs) -> "FluidState":
        d = {
            "m_dot": self.m_dot,
            "T": self.T,
            "p": self.p,
            "M": self.M,
            "model": self.model,
            "composition": self.composition,
        }
        d.update(kwargs)
        st = FluidState(**d)
        return st.update()
