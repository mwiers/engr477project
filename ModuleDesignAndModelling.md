
# ENGR477 Python Module Design and Modelling Document

This document describes the modelling methods and ideal coding structure and arcutecture of this module.

The goal of this module is to enable fast and efficient calulation and iteration of turbojet and turbojet-derived engines (turbofan, turboprop, etc.). This should be written using object-oriented-programming principles, with a focus on modularity and reusability of code. The module should be designed in a way that allows for easy extension to include additional engine components or more complex modelling methods in the future.

The main goal if the module is to analyze the Pratt & Whitney F135 Turbofan Engine, which is used in the F-35 Lightning II fighter jet. The module should be able to model the performance of this engine under various operating conditions and design parameters, and allow for easy iteration on these parameters to explore the performance of the engine under different scenarios.

## Inputs

In the main script, the goal is to be able to iterate on any of the paramters that define the engine or its operation conditions.
This involves defining the design parameters including, but not limited to:

- bypass ratio,
- the pressure ratio (for all compressors/turbines),
- the turbine inlet temperature,
- the mass flow rate,
- the fuel:air mass ratio,
- the altitude, ambient temperature/pressure, and speed of operation (which will affect the ambient conditions),
- the specific heat ratio of the working fluid (which may be a function of temperature and pressure).
- the efficiency of the various components (compressors, turbines, nozzles, etc.) in terms of either Pressure ratio or Isentropic efficiency.
- Combustion efficiency, which accounts for the fact that not all of the fuel's energy may be converted into useful work due to incomplete combustion or other losses, as a fraction between 0 and 1 directly applied to the fuel energy input.

The fluid properties should be calculated using a suitable method, such as the ideal gas law or more complex equations of state if necessary. The module should also account for changes in specific heat ratio with temperature and pressure, as well as any other relevant thermodynamic properties. This can be implemented using a separate class or module dedicated to fluid properties, which can be called by the main engine model to obtain the necessary properties at each stage of the engine.

Then the main script should be able to call the various functions and classes of components to allow the user to "build" the engine and calculate the state of the working fluid at each section in the engine, as well as the overall performance parameters such as thrust, specific fuel consumption, etc.
All of these details should be saved in a way that allows for easy access and analysis, such as in a structured data format (e.g., dictionaries, data classes, or custom objects).

## Model Specifications

### Fluid Modelling

The fluid modelling should be able to calculate the properties of the working fluid (air, fuel, and their mixture) at various stages of the engine. This includes calculating properties such as [static and stagnation values for] temperature, pressure, enthalpy, density, specific heat capacity, and specific heat ratio. The model should account for changes in these properties with temperature and pressure, and should be able to handle both ideal gas behavior and more complex equations of state if necessary. Generally air will be assumed to be an ideal gas, but the module should be flexible enough to allow for more complex modelling if desired. The fluid modelling can be implemented as a separate class or module that can be called by the main engine model to obtain the necessary properties at each stage of the engine.

### Engine Modelling

Each of the following components should be modelled as a separate class, with methods to calculate the state of the working fluid at the exit of the component based on the input state and the design parameters of the component. Each class should be completely modular and reusable (or able to be left out if not needed), allowing for easy extension to include additional components or more complex modelling methods in the future.

#### Inlet

Will be modelled as an adiabatic diffuser, which slows down the incoming air and increases its pressure. The model should account for the effects of altitude and speed on the ambient conditions, as well as any losses that may occur in the inlet as an isentropic efficiency (eta_diffuser or eta_inlet).

#### Fan

Will be modelled as

#### Bypass Duct (if applicable)

Will be modelled as

#### Compressor

Will be modelled as a (nearly) isentropic compressor, which increases the pressure of the working fluid. The model should account for isentropic efficiency (eta_compressor). Each stage of the compressor can be modelled separately, or the entire compressor can be modelled as a single component with an overall pressure ratio and efficiency.

#### Combustor

Will be modelled as a constant-pressure combustion chamber, which adds energy to the working fluid by burning fuel. The model should account for the fuel:air ratio, combustion efficiency, and the properties of the fuel being used. A pressure ratio across the combustor (P_out/P_in) should also be included to account for pressure losses in the combustor.

Other considerations for modelling the combustor include:

- One of the recommendations was to utilize NASA CEA as a subroutine for calculating the properties of the working fluid after combustion, which can be complex due to the chemical reactions and changes in composition that occur. This would allow for more accurate modelling of the combustor and its effects on the working fluid, as well as providing a way to easily calculate the properties of the exhaust gases for use in the turbine and nozzle calculations. This could be implemented by creating a wrapper function or class that interfaces with the NASA CEA code, allowing the user to input the necessary parameters (such as fuel type, fuel:air ratio or equivalence ratio, temperature, pressure, etc.) and receive the calculated properties of the working fluid after combustion.
- Another option is to use a Python CEA wrapper library, such as pyCEA, which provides a Python interface to the NASA CEA code. This would allow for easier integration of CEA calculations into the module without needing to write a custom wrapper function or class. Other Python libraries for thermodynamic calculations, such as Cantera, could also be considered for modelling the combustion process and calculating the properties of the working fluid after combustion.

#### Turbine

Will be modelled as a (nearly) isentropic turbine, which extracts energy from the working fluid to drive the compressor and fan. The model should account for isentropic efficiency (eta_turbine). Each stage of the turbine can be modelled separately, or the entire turbine can be modelled as a single component with an overall pressure ratio and efficiency.

The turbine work output should be calculated based on the work required to drive the compressor and fan, taking into account their efficiencies. The turbine inlet temperature should be defined as a design parameter, and the turbine outlet temperature should be calculated based on the energy balance of the turbine.

#### Mixer (if applicable)

Will be modelled as

#### Afterburner (if applicable)

Will be modelled as a constant-pressure combustion chamber, similar to the main combustor, but with the ability to add additional fuel to increase the temperature and energy of the working fluid before it enters the nozzle. The model should account for the fuel:air ratio, combustion efficiency, and the properties of the fuel being used. A pressure ratio across the afterburner (P_out/P_in) should also be included to account for pressure losses in the afterburner.

This component is only applicable for engines that have an afterburner, such as military fighter jet engines, and thus should be able to be optionally included in the engine model.

#### Nozzle

Will be modelled as a convergent or convergent-divergent nozzle, which accelerates the working fluid to produce thrust. The model should account for isentropic efficiency (eta_nozzle) and the ambient conditions, as well as any losses that may occur in the nozzle. This should be adaptable to handle both subsonic (unchoked) and supersonic (choked) exhaust velocities, depending on the design of the nozzle and the operating conditions of the engine.

## Desired Outputs

The main outputs of the module should include:

- The state of the working fluid at each stage of the engine (temperature, pressure, density, specific heat capacity, specific heat ratio, etc.).
- The overall performance parameters of the engine, such as thrust, specific fuel consumption, thermal efficiency, propulsive efficiency, etc.
- The ability to easily access and analyze the results, such as through structured data formats or custom objects that store the results in an organized manner.
- The ability to easily iterate on the design parameters and operating conditions to explore the performance of the engine under different scenarios.

The moduel is cosidered successful if it can accurately model the performance of the Pratt & Whitney F135 Turbofan Engine and allow for easy iteration on the design parameters and operating conditions to explore the performance of the engine under different scenarios.

## Suggested Architecture

The suggested architecture for the module is as follows:

- A main script that serves as the entry point for the user to define the design parameters and operating conditions, and to call the various classes and functions to build the engine and calculate the performance.
- A separate class or module for fluid properties, which can be called by the main engine model to obtain the necessary properties at each stage of the engine.
- Separate classes for each of the engine components (inlet, fan, bypass duct, compressor, combustor, turbine, mixer, afterburner, nozzle), each with methods to calculate the state of the working fluid at the exit of the component based on the input state and the design parameters of the component.
- A structured data format (e.g., dictionaries, data classes, or custom objects such as a ResultsContainer class or to have the Engine class store results in a structured way) to store the results of the calculations in an organized manner for easy access and analysis.
- A set of utility functions or methods for common calculations, such as calculating the specific heat ratio, specific heat capacity, or other thermodynamic properties based on the state of the working fluid.

Currently available architechture is as follows:

- engr477project/
  - main.py (main script for defining design/operation parameters, solving the engine model, and analyzing results)
  - fluid_properties.py (class or module for calculating fluid properties [class Fluid: ... & class Air(Fluid): ...])
  - results_container.py    (class for storing results in a structured way [class Result: ...])
  - utils.py    (utility functions for common calculations, such as calculating specific heat ratio, specific heat capacity, etc.)
  - engine.py (class for modelling the overall engine which calls the various component classes and stores results [class Engine: ...])
  - components/
    - component.py (base class for all components)
    - inlet.py
    - fan.py
    - bypass_duct.py
    - compressor.py
    - combustor.py
    - turbine.py
    - mixer.py
    - afterburner.py
    - nozzle.py
  - tools/
    - excel_writer.py (class or module for writing results to Excel files)
    - plotter.py  (utilities for plotting or heatmapping results when iterations are performed)
