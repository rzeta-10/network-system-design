import random

def generate_route():
    o1 = random.randint(1, 223)
    o2 = random.randint(0, 255)
    o3 = random.randint(0, 255)
    o4 = random.randint(0, 255)
    prefix_len = random.randint(8, 30)
    
    ip_int = (o1 << 24) | (o2 << 16) | (o3 << 8) | o4
    mask = ((1 << 32) - 1) << (32 - prefix_len) & 0xFFFFFFFF
    network_int = ip_int & mask
    
    net_str = f"{(network_int >> 24) & 0xFF}.{(network_int >> 16) & 0xFF}.{(network_int >> 8) & 0xFF}.{network_int & 0xFF}"
    return f"{net_str} {prefix_len} Router_{random.randint(1, 100)}"

def main():
    count = 10000
    print("0.0.0.0 0 Default_Gateway")
    for _ in range(count):
        print(generate_route())

if __name__ == "__main__":
    main()
