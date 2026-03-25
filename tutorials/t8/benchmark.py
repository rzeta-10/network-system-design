import time
import os
from input_gen import generate_traffic
from main import WFQScheduler

def run_benchmark():
    sizes = [1000, 5000, 10000, 50000, 100000]
    weights = {1: 5, 2: 3, 3: 2}
    
    print(f"{'Packets':<10} | {'Time (s)':<10}")
    print("-" * 25)
    
    for size in sizes:
        generate_traffic("bench_traffic.csv", size)
        
        start = time.time()
        scheduler = WFQScheduler(weights)
        scheduler.process_file("bench_traffic.csv")
        end = time.time()
        
        if os.path.exists("bench_traffic.csv"):
            os.remove("bench_traffic.csv")
            
        print(f"{size:<10} | {end - start:<10.4f}")

if __name__ == "__main__":
    run_benchmark()
