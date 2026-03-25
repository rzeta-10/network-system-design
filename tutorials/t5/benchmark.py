# CS22B1093 Rohan G

import time
import random
from mac_lookup import HashTable, mac_to_int, fold_mac_address

def run_benchmark(count=500, table_size=1024):
    print(f"Running Benchmark with {count} MAC addresses on Table Size {table_size}...")

    mac_addresses = []
    for _ in range(count):
        mac = [random.randint(0x00, 0xff) for _ in range(6)]
        mac_str = ":".join(f"{x:02X}" for x in mac)
        mac_addresses.append(mac_str)

    ht = HashTable(table_size)

    start_time = time.time()

    successful_inserts = 0
    failed_inserts = 0

    for mac in mac_addresses:
        mac_int = mac_to_int(mac)
        key = fold_mac_address(mac_int)
        result = ht.insert(key, mac)

        if result != -1:
            successful_inserts += 1
        else:
            failed_inserts += 1

    end_time = time.time()
    duration = end_time - start_time

    print(f"Time Taken: {duration:.6f} seconds")
    print(f"Successful Inserts: {successful_inserts}")
    print(f"Failed Inserts (Table Full): {failed_inserts}")
    print(f"Total Collisions: {ht.collisions}")
    print(f"Load Factor: {ht.count / table_size:.2f}")

    print("\nStarting Search Benchmark...")
    start_search = time.time()
    found_count = 0

    for mac in mac_addresses:
         key = fold_mac_address(mac_to_int(mac))
         val = ht.search(key)
         if val:
             found_count += 1

    end_search = time.time()
    print(f"Search Time for {count} items: {end_search - start_search:.6f} seconds")
    print(f"Items Found: {found_count}")

if __name__ == "__main__":
    test_cases = [100, 500, 800, 950, 1024, 1200]
    table_size = 1024
    
    print(f"Stress Testing with Table Size: {table_size}")
    print("=" * 60)

    for count in test_cases:
        print(f"\n--- Test Case: Inserting {count} Items ---")
        run_benchmark(count, table_size)
        print("-" * 60)
