

class Fluid:
    def __init__(self):
        pass


class Air(Fluid):
    def __init__(self, altitude, temperature, pressure):
        super().__init__()
        self.altitude = altitude
        self.temperature = temperature
        self.pressure = pressure