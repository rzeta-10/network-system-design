#!/usr/bin/env python3

from __future__ import annotations

import time
from pathlib import Path

from generate_inputs import generate_capture
from main import classify_packets, read_pcap_packets


def run_benchmark() -> None:
    base_dir = Path(__file__).resolve().parent
    sizes = [100, 1000, 5000, 10000]

    print(f"{'Packets':<10}{'Parsed':<10}{'Time (s)':<12}{'Throughput (pkt/s)'}")
    print("-" * 54)

    for size in sizes:
        capture_path = base_dir / f"benchmark_{size}.pcap"
        generate_capture(capture_path, benchmark_size=size)

        start = time.perf_counter()
        packets = read_pcap_packets(capture_path)
        classified = classify_packets(packets)
        elapsed = time.perf_counter() - start

        throughput = len(classified) / elapsed if elapsed > 0 else 0.0
        print(f"{size:<10}{len(classified):<10}{elapsed:<12.6f}{throughput:.2f}")

        if capture_path.exists():
            capture_path.unlink()


if __name__ == "__main__":
    run_benchmark()
