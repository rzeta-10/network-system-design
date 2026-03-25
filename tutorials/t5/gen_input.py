# CS22B1093 Rohan G

import random

def generate_mac_address():
    mac = [random.randint(0x00, 0xff) for _ in range(6)]
    return ":".join(map(lambda x: "%02x" % x, mac))

def generate_input_file(filename="mac_addresses.txt", count=1000):
    with open(filename, "w") as f:
        for _ in range(count):
            mac = generate_mac_address()
            f.write(mac + "\n")
    print(f"Generated {count} MAC addresses in {filename}")

if __name__ == "__main__":
    generate_input_file()
