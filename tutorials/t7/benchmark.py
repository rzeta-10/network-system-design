import time
import json
from main import calculate_fragmentation

def run_benchmark():
    try:
        with open("inputs.json", "r") as f:
            cases = json.load(f)
    except FileNotFoundError:
        return

    start_time = time.time()
    for case in cases:
        calculate_fragmentation(case["mtu1"], case["mtu2"])
    end_time = time.time()
    
    print(f"{len(cases)} cases | {end_time - start_time:.6f}s")

if __name__ == "__main__":
    run_benchmark()
