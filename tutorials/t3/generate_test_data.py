#!/usr/bin/env python3

# CS22B1093 Rohan G

import random
import json
import sys
import argparse
from datetime import datetime


def generate_multicast_ip():
    return f"{random.randint(224, 239)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}"


def generate_unicast_ip():
    first = random.randint(1, 223)
    # Avoid special ranges
    while first in [10, 127, 169, 172, 192]:
        first = random.randint(1, 223)
    return f"{first}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_test_scenario(num_groups, num_packets, wanted_ratio=0.3, seed=None):
    if seed is not None:
        random.seed(seed)
    
    joined_groups = []
    for _ in range(num_groups):
        ip = generate_multicast_ip()
        while ip in joined_groups:
            ip = generate_multicast_ip()
        joined_groups.append(ip)
    
    packets = []
    for _ in range(num_packets):
        source_ip = generate_unicast_ip()
        
        if random.random() < wanted_ratio:
            dest_ip = random.choice(joined_groups)
            is_wanted = True
        else:
            dest_ip = generate_multicast_ip()
            while dest_ip in joined_groups:
                dest_ip = generate_multicast_ip()
            is_wanted = False
        
        packets.append({
            'source': source_ip,
            'destination': dest_ip,
            'is_wanted': is_wanted
        })
    
    return {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'num_groups': num_groups,
            'num_packets': num_packets,
            'wanted_ratio': wanted_ratio,
            'seed': seed
        },
        'joined_groups': joined_groups,
        'packets': packets
    }


def generate_benchmark_configs():
    configs = []
    
    for num_groups in [5, 10, 20, 50]:
        configs.append({
            'name': f'groups_{num_groups}',
            'num_groups': num_groups,
            'num_packets': 5000,
            'wanted_ratio': 0.2,
            'filter_sizes': [64, 128, 256]
        })
    
    for wanted_ratio in [0.1, 0.3, 0.5, 0.7]:
        configs.append({
            'name': f'wanted_{int(wanted_ratio*100)}pct',
            'num_groups': 10,
            'num_packets': 5000,
            'wanted_ratio': wanted_ratio,
            'filter_sizes': [64, 128, 256]
        })
    
    configs.append({
        'name': 'heavy_load',
        'num_groups': 30,
        'num_packets': 10000,
        'wanted_ratio': 0.15,
        'filter_sizes': [64, 128, 256]
    })
    
    return configs


def print_scenario_summary(scenario):
    meta = scenario['metadata']
    
    print("=" * 60)
    print("TEST SCENARIO SUMMARY")
    print("=" * 60)
    print(f"Generated at: {meta['generated_at']}")
    print(f"Number of joined groups: {meta['num_groups']}")
    print(f"Number of packets: {meta['num_packets']}")
    print(f"Wanted traffic ratio: {meta['wanted_ratio']:.1%}")
    if meta['seed']:
        print(f"Random seed: {meta['seed']}")
    print()
    
    print("Joined Multicast Groups:")
    for i, group in enumerate(scenario['joined_groups'], 1):
        print(f"  {i:3d}. {group}")
    print()
    
    wanted_count = sum(1 for p in scenario['packets'] if p['is_wanted'])
    unwanted_count = len(scenario['packets']) - wanted_count
    
    print("Traffic Distribution:")
    print(f"  Wanted packets: {wanted_count}")
    print(f"  Unwanted packets: {unwanted_count}")
    print()


def save_scenario(scenario, filename):
    with open(filename, 'w') as f:
        json.dump(scenario, f, indent=2)
    print(f"Scenario saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate test data for multicast filter simulation'
    )
    
    parser.add_argument(
        '--groups', '-g',
        type=int, default=10,
        help='Number of multicast groups to join (default: 10)'
    )
    
    parser.add_argument(
        '--packets', '-p',
        type=int, default=1000,
        help='Number of packets to generate (default: 1000)'
    )
    
    parser.add_argument(
        '--wanted-ratio', '-w',
        type=float, default=0.3,
        help='Ratio of wanted traffic (0.0-1.0, default: 0.3)'
    )
    
    parser.add_argument(
        '--seed', '-s',
        type=int, default=None,
        help='Random seed for reproducibility'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str, default=None,
        help='Output JSON file (default: print to stdout)'
    )
    
    parser.add_argument(
        '--summary', '-S',
        action='store_true',
        help='Print human-readable summary instead of JSON'
    )
    
    parser.add_argument(
        '--benchmark-configs',
        action='store_true',
        help='Generate benchmark configurations'
    )
    
    args = parser.parse_args()
    
    if args.benchmark_configs:
        configs = generate_benchmark_configs()
        print(json.dumps(configs, indent=2))
        return
    
    scenario = generate_test_scenario(
        num_groups=args.groups,
        num_packets=args.packets,
        wanted_ratio=args.wanted_ratio,
        seed=args.seed
    )
    
    if args.summary:
        print_scenario_summary(scenario)
    elif args.output:
        save_scenario(scenario, args.output)
    else:
        print(json.dumps(scenario, indent=2))


if __name__ == '__main__':
    main()
