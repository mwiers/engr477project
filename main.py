


from enginemodels.F135model import F135Engine
from fluidmodels.idealgas import Air


def run():
    # Air properties: 
    air = Air( ... )            # Arguments like altitude, 
    engine = F135Engine(air,
                        ... )   # Arguments for various design parameters

    engine.solve()              # Engine stores data at each point between components
    
    
if __name__ == "__main__": 
    run()