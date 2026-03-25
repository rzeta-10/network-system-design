#!/usr/bin/env python3

# CS22B1093 Rohan G

import sys
import json
import time
import argparse
from datetime import datetime

from multicast_filter_simulation import (
    HardwareHashFilter,
    MulticastAddressMapper,
    CRC32Calculator
)
from generate_test_data import generate_test_scenario, generate_benchmark_configs


def run_single_benchmark(scenario, filter_size):
    hw_filter = HardwareHashFilter(table_size_bits=filter_size)
    
    for group_ip in scenario['joined_groups']:
        hw_filter.join_multicast_group(group_ip)
    
    start_time = time.perf_counter()
    
    for packet in scenario['packets']:
        hw_filter.process_incoming_packet(
            packet['source'],
            packet['destination']
        )
    
    elapsed_time = time.perf_counter() - start_time
    
    stats = hw_filter.get_statistics()
    
    total = stats['total_packets']
    hw_drops = stats['hardware_drops']
    hw_passes = stats['hardware_passes']
    sw_accepts = stats['software_accepts']
    sw_rejects = stats['false_positives']
    false_negatives = stats['false_negatives']
    
    true_negatives = hw_drops - false_negatives
    
    return {
        'filter_size': filter_size,
        'bits_set': stats['bits_set'],
        'bits_utilization': (stats['bits_set'] / filter_size) * 100,
        'total_packets': total,
        'hardware_drops': hw_drops,
        'hardware_passes': hw_passes,
        'software_accepts': sw_accepts,
        'false_positives': sw_rejects,
        'false_negatives': false_negatives,
        'true_negatives': true_negatives,
        'filtering_ratio': (hw_drops / total) * 100 if total > 0 else 0,
        'false_positive_rate': (sw_rejects / hw_passes) * 100 if hw_passes > 0 else 0,
        'false_negative_rate': (false_negatives / sw_accepts) * 100 if sw_accepts > 0 else 0,
        'packets_per_second': total / elapsed_time if elapsed_time > 0 else 0,
        'elapsed_time_ms': elapsed_time * 1000
    }


def run_full_benchmark(config, verbose=False):
    results = {
        'config_name': config['name'],
        'num_groups': config['num_groups'],
        'num_packets': config['num_packets'],
        'wanted_ratio': config['wanted_ratio'],
        'filter_results': []
    }
    
    scenario = generate_test_scenario(
        num_groups=config['num_groups'],
        num_packets=config['num_packets'],
        wanted_ratio=config['wanted_ratio'],
        seed=42
    )
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"Running benchmark: {config['name']}")
        print(f"  Groups: {config['num_groups']}")
        print(f"  Packets: {config['num_packets']}")
        print(f"  Wanted ratio: {config['wanted_ratio']:.1%}")
        print(f"{'='*60}")
    
    for filter_size in config['filter_sizes']:
        result = run_single_benchmark(scenario, filter_size)
        results['filter_results'].append(result)
        
        if verbose:
            print(f"\nFilter Size: {filter_size} bits")
            print(f"  Bits used: {result['bits_set']} ({result['bits_utilization']:.1f}%)")
            print(f"  HW Filtering Ratio: {result['filtering_ratio']:.2f}%")
            print(f"  False Positives: {result['false_positives']} ({result['false_positive_rate']:.2f}%)")
            print(f"  False Negatives: {result['false_negatives']} ({result['false_negative_rate']:.2f}%)")
            print(f"  Throughput: {result['packets_per_second']:.0f} packets/sec")
    
    return results


def print_summary_table(all_results):
    print("\n" + "=" * 110)
    print("BENCHMARK SUMMARY")
    print("=" * 110)
    
    print(f"{'Config':<18} {'Filter':<7} {'Groups':<7} {'HW Drop%':<10} {'FP':<6} {'FP%':<8} {'FN':<6} {'FN%':<8} {'Pkts/s':<10}")
    print("-" * 110)
    
    for bench in all_results:
        config_name = bench['config_name']
        num_groups = bench['num_groups']
        
        for fr in bench['filter_results']:
            print(f"{config_name:<18} {fr['filter_size']:<7} {num_groups:<7} "
                  f"{fr['filtering_ratio']:<10.2f} {fr['false_positives']:<6} {fr['false_positive_rate']:<8.2f} "
                  f"{fr['false_negatives']:<6} {fr['false_negative_rate']:<8.2f} {fr['packets_per_second']:<10.0f}")
    
    print("-" * 110)


def print_csv_output(all_results):
    print("config_name,filter_size,num_groups,num_packets,wanted_ratio,"
          "hw_drops,hw_passes,sw_accepts,false_positives,false_negatives,true_negatives,"
          "filtering_ratio,false_positive_rate,false_negative_rate,packets_per_sec")
    
    for bench in all_results:
        for fr in bench['filter_results']:
            print(f"{bench['config_name']},{fr['filter_size']},"
                  f"{bench['num_groups']},{bench['num_packets']},"
                  f"{bench['wanted_ratio']},"
                  f"{fr['hardware_drops']},{fr['hardware_passes']},"
                  f"{fr['software_accepts']},{fr['false_positives']},{fr['false_negatives']},{fr['true_negatives']},"
                  f"{fr['filtering_ratio']:.4f},{fr['false_positive_rate']:.4f},{fr['false_negative_rate']:.4f},"
                  f"{fr['packets_per_second']:.2f}")


def run_quick_benchmark():
    print("=" * 70)
    print("MULTICAST FILTER BENCHMARK")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    test_configs = [
        {'name': 'small_5groups', 'num_groups': 5, 'num_packets': 2000, 
         'wanted_ratio': 0.2, 'filter_sizes': [64, 128]},
        {'name': 'medium_10groups', 'num_groups': 10, 'num_packets': 3000, 
         'wanted_ratio': 0.25, 'filter_sizes': [64, 128]},
        {'name': 'large_20groups', 'num_groups': 20, 'num_packets': 5000, 
         'wanted_ratio': 0.2, 'filter_sizes': [64, 128]},
    ]
    
    all_results = []
    for config in test_configs:
        result = run_full_benchmark(config, verbose=True)
        all_results.append(result)
    
    print_summary_table(all_results)
    
    return all_results


def run_detailed_benchmark():
    print("=" * 70)
    print("DETAILED MULTICAST FILTER BENCHMARK")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    configs = generate_benchmark_configs()
    
    all_results = []
    for config in configs:
        result = run_full_benchmark(config, verbose=True)
        all_results.append(result)
    
    print_summary_table(all_results)
    
    return all_results


def main():
    parser = argparse.ArgumentParser(
        description='Run benchmarks for multicast filter simulation'
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['quick', 'detailed', 'custom'],
        default='quick',
        help='Benchmark mode: quick, detailed, or custom'
    )
    
    parser.add_argument(
        '--groups', '-g',
        type=int, default=10,
        help='Number of groups for custom mode'
    )
    
    parser.add_argument(
        '--packets', '-p',
        type=int, default=5000,
        help='Number of packets for custom mode'
    )
    
    parser.add_argument(
        '--filter-sizes', '-f',
        type=int, nargs='+',
        default=[64, 128, 256],
        help='Filter sizes to test'
    )
    
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Output results in CSV format'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'quick':
        results = run_quick_benchmark()
    elif args.mode == 'detailed':
        results = run_detailed_benchmark()
    else:
        config = {
            'name': 'custom',
            'num_groups': args.groups,
            'num_packets': args.packets,
            'wanted_ratio': 0.25,
            'filter_sizes': args.filter_sizes
        }
        results = [run_full_benchmark(config, verbose=True)]
        print_summary_table(results)
    
    if args.csv:
        print("\n" + "=" * 70)
        print("CSV OUTPUT")
        print("=" * 70)
        print_csv_output(results)
    
    if args.json:
        print("\n" + "=" * 70)
        print("JSON OUTPUT")
        print("=" * 70)
        print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
