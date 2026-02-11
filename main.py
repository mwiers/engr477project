


from engine import Engine
from fluid_properties import Air


def run():
    # Air properties: 
    air = Air(altitude=0, temperature=288.15, pressure=101325)
    # Arguments like altitude, temperature, pressure, etc. for calculating properties of the working fluid at the inlet of the engine

    engine = Engine(air,
                        ... )   
    # Arguments for various design parameters

    result = engine.solve()
    # Result stores data at each point between components
    
    
if __name__ == "__main__": 
    run()