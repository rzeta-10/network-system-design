# CS22B1093 Rohan G

import random

class HashTable:
    def __init__(self, size=1024):
        self.size = size
        self.table = [None] * size
        self.count = 0
        self.collisions = 0

    def hash1(self, key):
        return key % self.size

    def hash2(self, key):
        return 1 + (key % (self.size - 1))

    def insert(self, key, value):
        if self.count >= self.size:
            return -1

        index = self.hash1(key)

        if self.table[index] is None:
            self.table[index] = (key, value)
            self.count += 1
            return index

        self.collisions += 1
        step_size = self.hash2(key)
        original_index = index

        i = 1
        while True:
            new_index = (original_index + i * step_size) % self.size

            if self.table[new_index] is None:
                self.table[new_index] = (key, value)
                self.count += 1
                return new_index

            self.collisions += 1
            i += 1

            if i > self.size:
                return -1

    def search(self, key):
        index = self.hash1(key)

        if self.table[index] is not None and self.table[index][0] == key:
            return self.table[index][1]

        step_size = self.hash2(key)
        original_index = index
        i = 1

        while i <= self.size:
            new_index = (original_index + i * step_size) % self.size

            if self.table[new_index] is None:
                return None

            if self.table[new_index][0] == key:
                return self.table[new_index][1]

            i += 1

        return None

def mac_to_int(mac_str):
    hex_str = mac_str.replace(":", "")
    return int(hex_str, 16)

def fold_mac_address(mac_int):
    upper_32 = (mac_int >> 16) & 0xFFFFFFFF
    lower_16 = mac_int & 0xFFFF
    folded_key = upper_32 ^ lower_16
    return folded_key

def main():
    mac_table = HashTable(1024)

    sample_macs = [
        "00:1A:2B:3C:4D:5E",
        "A1:B2:C3:D4:E5:F6",
        "11:22:33:44:55:66",
        "FF:EE:DD:CC:BB:AA"
    ]

    print("-" * 60)
    print(f"{'MAC Address':<20} | {'Integer':<20} | {'Folded Key':<12} | {'Index'}")
    print("-" * 60)

    for mac in sample_macs:
        mac_int = mac_to_int(mac)
        folded = fold_mac_address(mac_int)
        index = mac_table.insert(folded, mac)

        print(f"{mac:<20} | {mac_int:<20} | {folded:<12} | {index}")

    print("-" * 60)
    print(f"\nSearching for {sample_macs[1]}:")

    search_key = fold_mac_address(mac_to_int(sample_macs[1]))
    result = mac_table.search(search_key)

    if result:
        print(f"Found: {result}")
    else:
        print("Not Found")

if __name__ == "__main__":
    main()
