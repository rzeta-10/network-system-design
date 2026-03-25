#!/usr/bin/env python3

# CS22B1093 Rohan G

import time
import statistics
from typing import List, Dict
import sys

from packet_buffer_manager import PacketBufferManager, OperationChainer
from generate_input import TrafficGenerator


class NaiveBufferManager:
    def __init__(self, buffer_size: int = 9000):
        self.buffer_size = buffer_size
        self.buffers = []
        self.packets_stored = 0
    
    def store_packet(self, packet_data: bytes) -> int:
        buffer = bytearray(self.buffer_size)
        buffer[:len(packet_data)] = packet_data
        self.buffers.append((buffer, len(packet_data)))
        self.packets_stored += 1
        return len(self.buffers) - 1
    
    def read_packet(self, index: int) -> bytes:
        buffer, actual_size = self.buffers[index]
        return bytes(buffer[:actual_size])
    
    def get_memory_usage(self) -> dict:
        total_allocated = len(self.buffers) * self.buffer_size
        total_used = sum(actual_size for _, actual_size in self.buffers)
        wasted = total_allocated - total_used
        
        return {
            'total_allocated': total_allocated,
            'total_used': total_used,
            'wasted': wasted,
            'fragmentation_pct': (wasted / total_allocated * 100) if total_allocated > 0 else 0,
            'num_buffers': len(self.buffers)
        }


class PerformanceBenchmark:
    def __init__(self, block_size: int = 512):
        self.block_size = block_size
        self.traffic_gen = TrafficGenerator(seed=42)
    
    def benchmark_fragmentation(self, packet_sizes: List[int]) -> Dict[str, dict]:
        chained_mgr = PacketBufferManager(block_size=self.block_size)
        chained_blocks_used = 0
        chained_bytes_used = 0
        
        for packet_size in packet_sizes:
            packet = b'X' * packet_size
            head = chained_mgr.write_packet(packet)
            
            current = head
            while current is not None:
                chained_blocks_used += 1
                chained_bytes_used += current.bytes_used
                current = current.next
            
            chained_mgr.free_packet(head)
        
        chained_allocated = chained_blocks_used * self.block_size
        chained_wasted = chained_allocated - chained_bytes_used
        chained_frag_pct = (chained_wasted / chained_allocated * 100) if chained_allocated > 0 else 0
        
        naive_mgr = NaiveBufferManager(buffer_size=9000)
        
        for packet_size in packet_sizes:
            packet = b'X' * packet_size
            naive_mgr.store_packet(packet)
        
        naive_stats = naive_mgr.get_memory_usage()
        
        memory_saved = naive_stats['total_allocated'] - chained_allocated
        memory_saved_pct = (memory_saved / naive_stats['total_allocated'] * 100) \
            if naive_stats['total_allocated'] > 0 else 0
        
        return {
            'chained': {
                'blocks_used': chained_blocks_used,
                'bytes_allocated': chained_allocated,
                'bytes_used': chained_bytes_used,
                'bytes_wasted': chained_wasted,
                'fragmentation_pct': chained_frag_pct
            },
            'naive': {
                'buffers_used': naive_stats['num_buffers'],
                'bytes_allocated': naive_stats['total_allocated'],
                'bytes_used': naive_stats['total_used'],
                'bytes_wasted': naive_stats['wasted'],
                'fragmentation_pct': naive_stats['fragmentation_pct']
            },
            'improvement': {
                'memory_saved_bytes': memory_saved,
                'memory_saved_pct': memory_saved_pct,
                'fragmentation_reduction': naive_stats['fragmentation_pct'] - chained_frag_pct
            }
        }
    
    def benchmark_throughput(self, packet_sizes: List[int], 
                            iterations: int = 3) -> Dict[str, dict]:
        chained_times = []
        naive_times = []
        
        test_packets = [b'X' * size for size in packet_sizes]
        
        for iteration in range(iterations):
            chained_mgr = PacketBufferManager(block_size=self.block_size)
            start = time.perf_counter()
            
            for packet in test_packets:
                head = chained_mgr.write_packet(packet)
                _ = chained_mgr.read_packet(head)
                chained_mgr.free_packet(head)
            
            chained_time = time.perf_counter() - start
            chained_times.append(chained_time)
            
            naive_mgr = NaiveBufferManager()
            start = time.perf_counter()
            
            for packet in test_packets:
                idx = naive_mgr.store_packet(packet)
                _ = naive_mgr.read_packet(idx)
            
            naive_time = time.perf_counter() - start
            naive_times.append(naive_time)
        
        chained_avg = statistics.mean(chained_times)
        naive_avg = statistics.mean(naive_times)
        
        chained_throughput = len(packet_sizes) / chained_avg
        naive_throughput = len(packet_sizes) / naive_avg
        
        total_bytes = sum(packet_sizes)
        chained_mbps = (total_bytes / chained_avg) / 1_000_000
        naive_mbps = (total_bytes / naive_avg) / 1_000_000
        
        return {
            'chained': {
                'avg_time_ms': chained_avg * 1000,
                'packets_per_sec': chained_throughput,
                'mbps': chained_mbps,
                'all_times': chained_times
            },
            'naive': {
                'avg_time_ms': naive_avg * 1000,
                'packets_per_sec': naive_throughput,
                'mbps': naive_mbps,
                'all_times': naive_times
            },
            'comparison': {
                'speedup': naive_avg / chained_avg if chained_avg > 0 else 0
            }
        }
    
    def benchmark_operation_chaining(self, packet_sizes: List[int]) -> Dict[str, dict]:
        manager = PacketBufferManager(block_size=self.block_size)
        
        zero_copy_times = []
        traditional_times = []
        
        for packet_size in packet_sizes:
            packet = b'X' * packet_size
            
            start = time.perf_counter()
            head = manager.write_packet(packet)
            crc = OperationChainer.compute_crc32(head)
            header = OperationChainer.parse_protocol_header(head, 16)
            manager.free_packet(head)
            zero_copy_time = time.perf_counter() - start
            zero_copy_times.append(zero_copy_time)
            
            start = time.perf_counter()
            head = manager.write_packet(packet)
            reassembled = manager.read_packet(head)
            
            import zlib
            crc_trad = zlib.crc32(reassembled)
            header_trad = reassembled[:16] if len(reassembled) >= 16 else b''
            
            manager.free_packet(head)
            traditional_time = time.perf_counter() - start
            traditional_times.append(traditional_time)
        
        zero_copy_avg = statistics.mean(zero_copy_times) * 1_000_000
        traditional_avg = statistics.mean(traditional_times) * 1_000_000
        
        speedup = traditional_avg / zero_copy_avg if zero_copy_avg > 0 else 0
        time_saved_pct = ((traditional_avg - zero_copy_avg) / traditional_avg * 100) \
            if traditional_avg > 0 else 0
        
        return {
            'zero_copy': {
                'avg_time_us': zero_copy_avg,
                'total_time_ms': sum(zero_copy_times) * 1000
            },
            'traditional': {
                'avg_time_us': traditional_avg,
                'total_time_ms': sum(traditional_times) * 1000
            },
            'improvement': {
                'speedup': speedup,
                'time_saved_pct': time_saved_pct
            }
        }
    
    def run_comprehensive_benchmark(self) -> Dict[str, dict]:
        test_scenarios = {
            'realistic': self.traffic_gen.generate_realistic(500),
            'bimodal': self.traffic_gen.generate_bimodal(500),
            'uniform': self.traffic_gen.generate_uniform(500, 64, 9000),
        }
        
        print("=" * 70)
        print("INPUT PACKET SIZES")
        print("=" * 70)
        for scenario_name, packet_sizes in test_scenarios.items():
            print(f"\n[{scenario_name.upper()}]")
            print(f"  Total packets: {len(packet_sizes)}")
            print(f"  Size range: {min(packet_sizes)} - {max(packet_sizes)} bytes")
            print(f"  Average size: {sum(packet_sizes) / len(packet_sizes):.1f} bytes")
            print(f"  First 20 sizes: {packet_sizes[:20]}")
        print("\n" + "=" * 70)
        
        all_results = {}
        
        for scenario_name, packet_sizes in test_scenarios.items():
            scenario_results = {
                'fragmentation': self.benchmark_fragmentation(packet_sizes[:100]),
                'throughput': self.benchmark_throughput(packet_sizes[:100]),
                'operation_chaining': self.benchmark_operation_chaining(packet_sizes[:50])
            }
            
            all_results[scenario_name] = scenario_results
        
        return all_results
    
    def print_summary_table(self, results: Dict[str, dict]):
        print(f"\n{'Fragmentation Comparison':^70}")
        print("-" * 70)
        print(f"{'Scenario':<15} {'Chained %':>12} {'Naive %':>12} {'Savings':>15}")
        print("-" * 70)
        
        for scenario, data in results.items():
            frag = data['fragmentation']
            print(f"{scenario:<15} "
                  f"{frag['chained']['fragmentation_pct']:>11.2f}% "
                  f"{frag['naive']['fragmentation_pct']:>11.2f}% "
                  f"{frag['improvement']['memory_saved_pct']:>14.1f}%")
        
        print(f"\n{'Throughput Comparison':^70}")
        print("-" * 70)
        print(f"{'Scenario':<15} {'Chained pkt/s':>15} {'Naive pkt/s':>15} {'Speedup':>12}")
        print("-" * 70)
        
        for scenario, data in results.items():
            tput = data['throughput']
            print(f"{scenario:<15} "
                  f"{tput['chained']['packets_per_sec']:>15.0f} "
                  f"{tput['naive']['packets_per_sec']:>15.0f} "
                  f"{tput['comparison']['speedup']:>11.2f}×")
        
        print(f"\n{'Operation Chaining Performance':^70}")
        print("-" * 70)
        print(f"{'Scenario':<15} {'Zero-Copy µs':>15} {'Traditional µs':>17} {'Speedup':>12}")
        print("-" * 70)
        
        for scenario, data in results.items():
            ops = data['operation_chaining']
            print(f"{scenario:<15} "
                  f"{ops['zero_copy']['avg_time_us']:>15.2f} "
                  f"{ops['traditional']['avg_time_us']:>17.2f} "
                  f"{ops['improvement']['speedup']:>11.2f}×")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark(block_size=512)
    results = benchmark.run_comprehensive_benchmark()
    benchmark.print_summary_table(results)
