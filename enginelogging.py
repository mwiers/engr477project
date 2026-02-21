global VERBOSE
VERBOSE = True


class ProgressBar:
    def __init__(self, total: int):
        self.total = total
        self.current = 0

    def update(self, increment: int = 1):
        self.current += increment
        empty = "-"
        full = "█"
        total_bars = 25
        filled_bars = int(self.current / self.total * total_bars)
        empty_bars = total_bars - filled_bars
        bar = full * filled_bars + empty * empty_bars
        
        if self.current == self.total:
            endline = "\n"
        else: 
            endline = "\r"
        print(f"Progress: [{bar}] {self.current}/{self.total}", end=endline)

        
