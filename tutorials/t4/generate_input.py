#!/usr/bin/env python3

# CS22B1093 Rohan G

import random
import json
from typing import List


class TrafficGenerator:
    COMMON_SIZES = [64, 128, 256, 512, 576, 1024, 1460, 1500, 4096, 9000]
    
    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
    
    def generate_uniform(self, count: int, min_size: int = 64, 
                        max_size: int = 9000) -> List[int]:
        return [random.randint(min_size, max_size) for _ in range(count)]
    
    def generate_bimodal(self, count: int, small_ratio: float = 0.7) -> List[int]:
        sizes = []
        for _ in range(count):
            if random.random() < small_ratio:
                sizes.append(random.randint(64, 128))
            else:
                sizes.append(random.randint(1400, 1500))
        return sizes
    
    def generate_realistic(self, count: int) -> List[int]:
        sizes = []
        for _ in range(count):
            category = random.random()
            if category < 0.5:
                sizes.append(random.randint(64, 256))
            elif category < 0.8:
                sizes.append(random.randint(256, 1024))
            else:
                sizes.append(random.randint(1024, 1500))
        return sizes
    
    def generate_common_sizes(self, count: int) -> List[int]:
        return [random.choice(self.COMMON_SIZES) for _ in range(count)]
    
    def generate_edge_cases(self) -> List[int]:
        return [1, 63, 64, 255, 256, 511, 512, 513, 1023, 1024, 1500, 4096, 9000]
    
    def generate_burst(self, burst_size: int, packet_size: int, 
                      num_bursts: int, gap_packets: int = 5) -> List[int]:
        sizes = []
        for _ in range(num_bursts):
            sizes.extend([packet_size] * burst_size)
            sizes.extend([random.randint(64, 128) for _ in range(gap_packets)])
        return sizes
    
    def create_test_dataset(self, output_file: str = None) -> dict:
        dataset = {
            'uniform_small': {
                'description': 'Uniform distribution, small packets (64-512 bytes)',
                'sizes': self.generate_uniform(100, 64, 512)
            },
            'uniform_large': {
                'description': 'Uniform distribution, large packets (512-9000 bytes)',
                'sizes': self.generate_uniform(100, 512, 9000)
            },
            'uniform_full': {
                'description': 'Uniform distribution, full range (64-9000 bytes)',
                'sizes': self.generate_uniform(200, 64, 9000)
            },
            'bimodal_70_30': {
                'description': 'Bimodal: 70% small (64-128), 30% large (1400-1500)',
                'sizes': self.generate_bimodal(200, 0.7)
            },
            'realistic': {
                'description': 'Realistic internet traffic pattern',
                'sizes': self.generate_realistic(300)
            },
            'common_sizes': {
                'description': 'Common real-world packet sizes only',
                'sizes': self.generate_common_sizes(150)
            },
            'edge_cases': {
                'description': 'Edge case packet sizes for boundary testing',
                'sizes': self.generate_edge_cases()
            },
            'video_stream': {
                'description': 'Bursty video streaming pattern',
                'sizes': self.generate_burst(10, 1460, 20, 5)
            },
            'bulk_transfer': {
                'description': 'Sustained large packet transfer (file download)',
                'sizes': [1460] * 100
            }
        }
        
        for scenario_name, scenario_data in dataset.items():
            sizes = scenario_data['sizes']
            scenario_data['statistics'] = {
                'count': len(sizes),
                'total_bytes': sum(sizes),
                'min_size': min(sizes),
                'max_size': max(sizes),
                'avg_size': sum(sizes) / len(sizes),
                'median_size': sorted(sizes)[len(sizes) // 2]
            }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(dataset, f, indent=2)
        
        return dataset
