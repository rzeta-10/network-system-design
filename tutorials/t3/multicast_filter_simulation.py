#!/usr/bin/env python3

# CS22B1093 Rohan G

import random
from typing import List, Set, Dict

class CRC32Calculator:
    POLYNOMIAL = 0xEDB88320
    
    def __init__(self):
        self.lookup_table = self.build_lookup_table()
    
    def build_lookup_table(self) -> List[int]:
        table = []
        for byte_val in range(256):
            crc = byte_val
            for _ in range(8):
                if crc & 1: 
                    crc = (crc >> 1) ^ self.POLYNOMIAL
                else:
                    crc = crc >> 1
            table.append(crc)
        return table
    
    def compute(self, data: bytes) -> int:
        crc = 0xFFFFFFFF
        for byte in data:
            table_index = (crc ^ byte) & 0xFF
            crc = (crc >> 8) ^ self.lookup_table[table_index]
        return crc ^ 0xFFFFFFFF


class MulticastAddressMapper:
    MAC_PREFIX = bytes([0x01, 0x00, 0x5E])
    
    @staticmethod
    def is_valid_multicast_ip(ip_address: str) -> bool:
        try:
            octets = [int(x) for x in ip_address.split('.')]
            if len(octets) != 4:
                return False
            return 224 <= octets[0] <= 239
        except (ValueError, AttributeError):
            return False
    
    @staticmethod
    def ip_to_mac(ip_address: str) -> str:
        octets = [int(x) for x in ip_address.split('.')]
        mac_byte_4 = octets[1] & 0x7F
        mac_byte_5 = octets[2]
        mac_byte_6 = octets[3]
        return "01:00:5E:{:02X}:{:02X}:{:02X}".format(mac_byte_4, mac_byte_5, mac_byte_6)
    
    @staticmethod
    def mac_to_bytes(mac_address: str) -> bytes:
        clean_mac = mac_address.replace(':', '').replace('-', '')
        return bytes.fromhex(clean_mac)
    
    @staticmethod
    def generate_random_multicast_ip() -> str:
        return f"{random.randint(224, 239)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"


class HardwareHashFilter:
    def __init__(self, table_size_bits: int = 64):
        self.table_size = table_size_bits
        self.bit_mask = table_size_bits - 1
        self.filter_table: Set[int] = set()
        self.joined_groups: Set[str] = set()
        self.crc_calc = CRC32Calculator()
        self.stats = {
            'total_received': 0,
            'hardware_drops': 0,
            'hardware_passes': 0,
            'software_accepts': 0,
            'software_rejects': 0,
            'false_negatives': 0,
        }
    
    def compute_hash_index(self, mac_address: bytes) -> int:
        crc = self.crc_calc.compute(mac_address)
        if self.table_size == 64:
            return (crc >> 26) & 0x3F
        elif self.table_size == 128:
            return (crc >> 25) & 0x7F
        else:
            import math
            bits_needed = int(math.log2(self.table_size))
            return (crc >> (32 - bits_needed)) & self.bit_mask
    
    def join_multicast_group(self, ip_address: str) -> Dict:
        mac_address = MulticastAddressMapper.ip_to_mac(ip_address)
        mac_bytes = MulticastAddressMapper.mac_to_bytes(mac_address)
        hash_index = self.compute_hash_index(mac_bytes)
        self.filter_table.add(hash_index)
        self.joined_groups.add(ip_address)
        return {'ip_address': ip_address, 'mac_address': mac_address, 'hash_index': hash_index}
    
    def process_incoming_packet(self, source_ip: str, dest_ip: str) -> Dict:
        self.stats['total_received'] += 1
        dest_mac = MulticastAddressMapper.ip_to_mac(dest_ip)
        dest_mac_bytes = MulticastAddressMapper.mac_to_bytes(dest_mac)
        hash_index = self.compute_hash_index(dest_mac_bytes)
        is_wanted = dest_ip in self.joined_groups
        
        result = {
            'dest_ip': dest_ip,
            'dest_mac': dest_mac,
            'hash_index': hash_index,
            'hardware_decision': None,
            'software_decision': None,
            'is_false_positive': False,
            'is_false_negative': False,
        }
        
        if hash_index not in self.filter_table:
            self.stats['hardware_drops'] += 1
            result['hardware_decision'] = 'DROP'
            if is_wanted:
                self.stats['false_negatives'] += 1
                result['is_false_negative'] = True
            return result
        
        self.stats['hardware_passes'] += 1
        result['hardware_decision'] = 'PASS'
        
        if dest_ip in self.joined_groups:
            self.stats['software_accepts'] += 1
            result['software_decision'] = 'ACCEPT'
        else:
            self.stats['software_rejects'] += 1
            result['software_decision'] = 'REJECT'
            result['is_false_positive'] = True
        
        return result
    
    def get_statistics(self) -> Dict:
        total = self.stats['total_received']
        if total == 0:
            return {'error': 'No packets processed'}
        
        hw_drops = self.stats['hardware_drops']
        hw_passes = self.stats['hardware_passes']
        sw_rejects = self.stats['software_rejects']
        
        return {
            'total_packets': total,
            'hardware_drops': hw_drops,
            'hardware_passes': hw_passes,
            'software_accepts': self.stats['software_accepts'],
            'false_positives': sw_rejects,
            'false_negatives': self.stats['false_negatives'],
            'filtering_ratio': (hw_drops / total) * 100,
            'false_positive_rate': (sw_rejects / hw_passes * 100) if hw_passes > 0 else 0,
            'bits_set': len(self.filter_table),
        }


def run_simulation(filter_size=64, num_groups=10, num_packets=5000, wanted_ratio=0.2):
    print("=" * 70)
    print("MULTICAST NIC HARDWARE FILTER SIMULATION")
    print("=" * 70)
    
    print(f"\nConfiguration:")
    print(f"  Filter Size: {filter_size} bits")
    print(f"  Groups to Join: {num_groups}")
    print(f"  Packets to Process: {num_packets}")
    print(f"  Wanted Traffic Ratio: {wanted_ratio*100}%")
    
    # Demonstrate IP to MAC mapping
    print("\n" + "-" * 50)
    print("IP to MAC Address Mapping (32 IPs share 1 MAC):")
    print("-" * 50)
    demo_ips = ["224.1.1.1", "224.129.1.1", "239.1.1.1"]
    for ip in demo_ips:
        mac = MulticastAddressMapper.ip_to_mac(ip)
        print(f"  {ip:15} -> {mac}")
    
    # Create filter and join groups
    hw_filter = HardwareHashFilter(table_size_bits=filter_size)
    
    print("\n" + "-" * 50)
    print("Joining Multicast Groups:")
    print("-" * 50)
    
    joined_ips = []
    for i in range(num_groups):
        ip = MulticastAddressMapper.generate_random_multicast_ip()
        while ip in joined_ips:
            ip = MulticastAddressMapper.generate_random_multicast_ip()
        result = hw_filter.join_multicast_group(ip)
        joined_ips.append(ip)
        print(f"  [{i+1:2}] {ip:18} -> MAC: {result['mac_address']}  Hash: {result['hash_index']}")
    
    print(f"\nBits set in filter: {len(hw_filter.filter_table)} / {filter_size}")
    
    # Process packets
    print("\n" + "-" * 50)
    print(f"Processing {num_packets} packets...")
    print("-" * 50)
    
    for _ in range(num_packets):
        if random.random() < wanted_ratio:
            dest_ip = random.choice(joined_ips)
        else:
            dest_ip = MulticastAddressMapper.generate_random_multicast_ip()
            while dest_ip in joined_ips:
                dest_ip = MulticastAddressMapper.generate_random_multicast_ip()
        
        src_ip = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
        hw_filter.process_incoming_packet(src_ip, dest_ip)
    
    # Display results
    stats = hw_filter.get_statistics()
    
    print("\nRESULTS:")
    print("=" * 50)
    print(f"  Total Packets:        {stats['total_packets']}")
    print(f"  Hardware Drops:       {stats['hardware_drops']}")
    print(f"  Hardware Passes:      {stats['hardware_passes']}")
    print(f"  Software Accepts:     {stats['software_accepts']}")
    print(f"  False Positives:      {stats['false_positives']}")
    print(f"  False Negatives:      {stats['false_negatives']}")
    print()
    print(f"  Filtering Ratio:      {stats['filtering_ratio']:.2f}%")
    print(f"  False Positive Rate:  {stats['false_positive_rate']:.2f}%")
    print("=" * 50)
    
    return stats


def compare_filter_sizes():
    print("\n" + "=" * 70)
    print("FILTER SIZE COMPARISON")
    print("=" * 70)
    
    sizes = [64, 128, 256]
    results = []
    
    for size in sizes:
        random.seed(42)
        hw_filter = HardwareHashFilter(table_size_bits=size)
        
        joined = []
        for _ in range(10):
            ip = MulticastAddressMapper.generate_random_multicast_ip()
            hw_filter.join_multicast_group(ip)
            joined.append(ip)
        
        random.seed(123)
        for _ in range(5000):
            if random.random() < 0.2:
                dest = random.choice(joined)
            else:
                dest = MulticastAddressMapper.generate_random_multicast_ip()
            src = f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
            hw_filter.process_incoming_packet(src, dest)
        
        stats = hw_filter.get_statistics()
        results.append({'size': size, **stats})
    
    print(f"\n{'Filter':<10} {'HW Drop%':<12} {'FP Count':<10} {'FP Rate%':<12}")
    print("-" * 50)
    for r in results:
        print(f"{r['size']:<10} {r['filtering_ratio']:<12.2f} {r['false_positives']:<10} {r['false_positive_rate']:<12.2f}")
    print("-" * 50)


if __name__ == "__main__":
    run_simulation(filter_size=64, num_groups=10, num_packets=3000)
    compare_filter_sizes()
