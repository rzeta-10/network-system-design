#!/usr/bin/env python3

from __future__ import annotations

import argparse
import random
import socket
import struct
from pathlib import Path


TCP_PROTOCOL = 6
UDP_PROTOCOL = 17
ICMP_PROTOCOL = 1
ETHERNET_HEADER = bytes.fromhex("00112233445566778899aabb0800")


def checksum(data: bytes) -> int:
    if len(data) % 2 == 1:
        data += b"\x00"

    total = 0
    for index in range(0, len(data), 2):
        total += (data[index] << 8) + data[index + 1]
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def ipv4_header(src_ip: str, dst_ip: str, protocol: int, payload_length: int, identification: int) -> bytes:
    version_ihl = 0x45
    total_length = 20 + payload_length
    src_raw = socket.inet_aton(src_ip)
    dst_raw = socket.inet_aton(dst_ip)

    header = struct.pack(
        "!BBHHHBBH4s4s",
        version_ihl,
        0,
        total_length,
        identification,
        0,
        64,
        protocol,
        0,
        src_raw,
        dst_raw,
    )
    header_checksum = checksum(header)
    return struct.pack(
        "!BBHHHBBH4s4s",
        version_ihl,
        0,
        total_length,
        identification,
        0,
        64,
        protocol,
        header_checksum,
        src_raw,
        dst_raw,
    )


def tcp_segment(
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    flags: int,
    seq_no: int,
    ack_no: int,
    payload: bytes,
) -> bytes:
    data_offset = 5 << 4
    header = struct.pack(
        "!HHLLBBHHH",
        src_port,
        dst_port,
        seq_no,
        ack_no,
        data_offset,
        flags,
        4096,
        0,
        0,
    )
    pseudo_header = struct.pack(
        "!4s4sBBH",
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
        0,
        TCP_PROTOCOL,
        len(header) + len(payload),
    )
    segment_checksum = checksum(pseudo_header + header + payload)
    header = struct.pack(
        "!HHLLBBHHH",
        src_port,
        dst_port,
        seq_no,
        ack_no,
        data_offset,
        flags,
        4096,
        segment_checksum,
        0,
    )
    return header + payload


def udp_datagram(src_ip: str, dst_ip: str, src_port: int, dst_port: int, payload: bytes) -> bytes:
    length = 8 + len(payload)
    header = struct.pack("!HHHH", src_port, dst_port, length, 0)
    pseudo_header = struct.pack(
        "!4s4sBBH",
        socket.inet_aton(src_ip),
        socket.inet_aton(dst_ip),
        0,
        UDP_PROTOCOL,
        length,
    )
    datagram_checksum = checksum(pseudo_header + header + payload)
    header = struct.pack("!HHHH", src_port, dst_port, length, datagram_checksum)
    return header + payload


def icmp_message(payload: bytes, sequence_no: int) -> bytes:
    header = struct.pack("!BBHHH", 8, 0, 0, 1, sequence_no)
    message_checksum = checksum(header + payload)
    return struct.pack("!BBHHH", 8, 0, message_checksum, 1, sequence_no) + payload


def build_frame(spec: dict, identification: int) -> bytes:
    payload = bytes(spec["payload"])
    protocol = spec["protocol"]

    if protocol == "TCP":
        transport = tcp_segment(
            spec["src_ip"],
            spec["dst_ip"],
            spec["src_port"],
            spec["dst_port"],
            spec.get("flags", 0x18),
            spec.get("seq_no", identification * 100),
            spec.get("ack_no", 0),
            payload,
        )
        protocol_number = TCP_PROTOCOL
    elif protocol == "UDP":
        transport = udp_datagram(
            spec["src_ip"],
            spec["dst_ip"],
            spec["src_port"],
            spec["dst_port"],
            payload,
        )
        protocol_number = UDP_PROTOCOL
    else:
        transport = icmp_message(payload, identification)
        protocol_number = ICMP_PROTOCOL

    ip = ipv4_header(
        spec["src_ip"], spec["dst_ip"], protocol_number, len(transport), identification
    )
    return ETHERNET_HEADER + ip + transport


def write_pcap(output_path: Path, packet_specs: list[dict]) -> None:
    with output_path.open("wb") as handle:
        handle.write(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))

        for identification, spec in enumerate(packet_specs, start=1):
            frame = build_frame(spec, identification)
            timestamp = spec["timestamp"]
            seconds = int(timestamp)
            microseconds = int((timestamp - seconds) * 1_000_000)
            handle.write(
                struct.pack("<IIII", seconds, microseconds, len(frame), len(frame))
            )
            handle.write(frame)


def add_tcp_series(
    packet_specs: list[dict],
    start_time: float,
    count: int,
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    payload_text: str,
    step: float = 0.05,
) -> float:
    for offset in range(count):
        packet_specs.append(
            {
                "timestamp": start_time + (offset * step),
                "protocol": "TCP",
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port + offset,
                "dst_port": dst_port,
                "flags": 0x18,
                "payload": payload_text.encode("utf-8"),
            }
        )
    return start_time + (count * step)


def add_udp_series(
    packet_specs: list[dict],
    start_time: float,
    count: int,
    src_ip: str,
    dst_ip: str,
    src_port: int,
    dst_port: int,
    payload_text: str,
    step: float = 0.05,
) -> float:
    for offset in range(count):
        packet_specs.append(
            {
                "timestamp": start_time + (offset * step),
                "protocol": "UDP",
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port + offset,
                "dst_port": dst_port,
                "payload": payload_text.encode("utf-8"),
            }
        )
    return start_time + (count * step)


def build_demo_capture() -> list[dict]:
    packet_specs: list[dict] = []
    current_time = 1.0

    current_time = add_tcp_series(
        packet_specs, current_time, 5, "10.0.0.10", "93.184.216.34", 40000, 80, "GET /"
    )
    current_time = add_tcp_series(
        packet_specs, current_time + 0.1, 4, "10.0.0.11", "172.217.167.78", 41000, 443, "TLS"
    )
    current_time = add_tcp_series(
        packet_specs, current_time + 0.1, 3, "10.0.0.12", "198.51.100.20", 42000, 21, "USER"
    )
    current_time = add_tcp_series(
        packet_specs, current_time + 0.1, 2, "10.0.0.13", "198.51.100.30", 43000, 25, "MAIL"
    )
    current_time = add_udp_series(
        packet_specs, current_time + 0.1, 4, "10.0.0.14", "8.8.8.8", 44000, 53, "DNS?"
    )

    packet_specs.append(
        {
            "timestamp": current_time + 0.1,
            "protocol": "UDP",
            "src_ip": "10.0.0.15",
            "dst_ip": "192.0.2.55",
            "src_port": 45000,
            "dst_port": 5060,
            "payload": b"SIP",
        }
    )
    packet_specs.append(
        {
            "timestamp": current_time + 0.15,
            "protocol": "UDP",
            "src_ip": "10.0.0.15",
            "dst_ip": "192.0.2.55",
            "src_port": 45010,
            "dst_port": 12000,
            "payload": b"RTP",
        }
    )

    scan_ports = [22, 23, 80, 111, 135, 139]
    for offset, port in enumerate(scan_ports):
        packet_specs.append(
            {
                "timestamp": current_time + 0.3 + (offset * 0.04),
                "protocol": "TCP",
                "src_ip": "10.9.9.9",
                "dst_ip": "192.168.1.10",
                "src_port": 46000 + offset,
                "dst_port": port,
                "flags": 0x02,
                "payload": b"",
            }
        )

    for offset in range(7):
        packet_specs.append(
            {
                "timestamp": current_time + 0.8 + (offset * 0.05),
                "protocol": "UDP",
                "src_ip": "10.0.0.20",
                "dst_ip": "192.168.1.20",
                "src_port": 47000 + offset,
                "dst_port": 40000,
                "payload": b"odd-port",
            }
        )

    packet_specs.append(
        {
            "timestamp": current_time + 1.4,
            "protocol": "TCP",
            "src_ip": "203.0.113.250",
            "dst_ip": "192.168.1.25",
            "src_port": 48000,
            "dst_port": 8080,
            "flags": 0x18,
            "payload": b"blocked",
        }
    )
    packet_specs.append(
        {
            "timestamp": current_time + 1.5,
            "protocol": "ICMP",
            "src_ip": "10.0.0.30",
            "dst_ip": "1.1.1.1",
            "payload": b"ping-demo",
        }
    )

    return packet_specs


def build_benchmark_capture(packet_count: int) -> list[dict]:
    random.seed(7)
    packet_specs: list[dict] = []
    destinations = [
        ("93.184.216.34", "TCP", 80, b"GET /bench"),
        ("172.217.167.78", "TCP", 443, b"TLS"),
        ("198.51.100.40", "UDP", 53, b"DNS"),
        ("192.0.2.80", "UDP", 5060, b"SIP"),
        ("192.168.1.60", "UDP", 40000, b"unknown"),
    ]

    for index in range(packet_count):
        dst_ip, protocol, dst_port, payload = destinations[index % len(destinations)]
        timestamp = 1.0 + (index * 0.002)
        spec = {
            "timestamp": timestamp,
            "protocol": protocol,
            "src_ip": f"10.0.{(index // 250) % 10}.{(index % 200) + 1}",
            "dst_ip": dst_ip,
            "src_port": 30000 + (index % 2000),
            "dst_port": dst_port,
            "payload": payload,
        }
        if protocol == "TCP":
            spec["flags"] = 0x18

        packet_specs.append(spec)

    for offset, port in enumerate([30, 31, 32, 33, 34, 35]):
        packet_specs.append(
            {
                "timestamp": 20.0 + (offset * 0.03),
                "protocol": "TCP",
                "src_ip": "198.18.0.10",
                "dst_ip": "192.168.10.10",
                "src_port": 50000 + offset,
                "dst_port": port,
                "flags": 0x02,
                "payload": b"",
            }
        )

    for offset in range(8):
        packet_specs.append(
            {
                "timestamp": 25.0 + (offset * 0.04),
                "protocol": "UDP",
                "src_ip": "198.18.0.20",
                "dst_ip": "192.168.10.20",
                "src_port": 52000 + offset,
                "dst_port": 45000,
                "payload": b"burst",
            }
        )

    packet_specs.append(
        {
            "timestamp": 30.0,
            "protocol": "TCP",
            "src_ip": "203.0.113.250",
            "dst_ip": "192.168.10.30",
            "src_port": 53000,
            "dst_port": 9000,
            "flags": 0x18,
            "payload": b"blacklisted",
        }
    )

    return packet_specs


def generate_capture(output_path: Path, benchmark_size: int | None = None) -> Path:
    if benchmark_size is None:
        packet_specs = build_demo_capture()
    else:
        packet_specs = build_benchmark_capture(benchmark_size)

    write_pcap(output_path, packet_specs)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate sample pcap inputs for the tutorial 9 packet classifier."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("sample_packets.pcap"),
        help="Path to the output pcap file.",
    )
    parser.add_argument(
        "-n",
        "--benchmark-size",
        type=int,
        help="If provided, generate a larger benchmark capture with this many base packets.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    output_path = generate_capture(args.output, args.benchmark_size)
    print(f"Capture written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
