#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


PCAP_MAGIC_INFO = {
    b"\xd4\xc3\xb2\xa1": ("<", 1_000_000),
    b"\xa1\xb2\xc3\xd4": (">", 1_000_000),
    b"\x4d\x3c\xb2\xa1": ("<", 1_000_000_000),
    b"\xa1\xb2\x3c\x4d": (">", 1_000_000_000),
}

PROTOCOL_NAMES = {1: "ICMP", 6: "TCP", 17: "UDP"}
KNOWN_PORTS = {
    20,
    21,
    22,
    23,
    25,
    53,
    67,
    68,
    80,
    110,
    123,
    143,
    161,
    389,
    443,
    445,
    587,
    993,
    995,
    3306,
    3389,
    5060,
}

CLASS_PRIORITY = {
    "Unclassified Traffic": 0,
    "ICMP Traffic": 1,
    "HTTP Traffic": 2,
    "HTTPS Traffic": 2,
    "FTP Traffic": 2,
    "SMTP Traffic": 2,
    "DNS Traffic": 2,
    "VoIP Traffic": 2,
    "Suspicious Traffic": 3,
    "Port Scan Attack": 4,
    "Malicious Traffic": 5,
}


@dataclass
class PacketRecord:
    packet_no: int
    timestamp: float
    src_ip: str
    dst_ip: str
    protocol: str
    src_port: int | None
    dst_port: int | None
    packet_size: int
    tcp_flags: str


@dataclass
class ClassifiedPacket:
    packet_no: int
    timestamp: float
    src_ip: str
    dst_ip: str
    protocol: str
    src_port: int | None
    dst_port: int | None
    packet_size: int
    tcp_flags: str
    traffic_class: str
    reason: str


def tcp_flags_to_text(flags: int) -> str:
    names = []
    if flags & 0x02:
        names.append("SYN")
    if flags & 0x10:
        names.append("ACK")
    if flags & 0x01:
        names.append("FIN")
    if flags & 0x04:
        names.append("RST")
    if flags & 0x08:
        names.append("PSH")
    if flags & 0x20:
        names.append("URG")
    return ",".join(names) if names else "-"


def read_pcap_packets(file_path: Path) -> list[PacketRecord]:
    packets: list[PacketRecord] = []

    with file_path.open("rb") as handle:
        magic = handle.read(4)
        if magic not in PCAP_MAGIC_INFO:
            raise ValueError("Unsupported capture file format. Use a .pcap file.")

        endian, time_scale = PCAP_MAGIC_INFO[magic]
        rest = handle.read(20)
        if len(rest) != 20:
            raise ValueError("Incomplete pcap global header.")

        packet_no = 1
        while True:
            header = handle.read(16)
            if not header:
                break
            if len(header) != 16:
                raise ValueError("Incomplete per-packet header in capture file.")

            ts_sec, ts_frac, incl_len, _orig_len = struct.unpack(
                f"{endian}IIII", header
            )
            raw_packet = handle.read(incl_len)
            if len(raw_packet) != incl_len:
                raise ValueError("Capture file ended in the middle of a packet.")

            parsed = parse_ethernet_frame(
                raw_packet, packet_no, ts_sec + (ts_frac / time_scale)
            )
            if parsed is not None:
                packets.append(parsed)
                packet_no += 1

    return packets


def parse_ethernet_frame(
    raw_packet: bytes, packet_no: int, timestamp: float
) -> PacketRecord | None:
    if len(raw_packet) < 14:
        return None

    ether_type = struct.unpack("!H", raw_packet[12:14])[0]
    if ether_type != 0x0800:
        return None

    return parse_ipv4_packet(raw_packet[14:], packet_no, timestamp)


def parse_ipv4_packet(
    raw_ip_packet: bytes, packet_no: int, timestamp: float
) -> PacketRecord | None:
    if len(raw_ip_packet) < 20:
        return None

    version_ihl = raw_ip_packet[0]
    version = version_ihl >> 4
    if version != 4:
        return None

    ip_header_length = (version_ihl & 0x0F) * 4
    if len(raw_ip_packet) < ip_header_length or ip_header_length < 20:
        return None

    total_length = struct.unpack("!H", raw_ip_packet[2:4])[0]
    protocol_number = raw_ip_packet[9]
    src_ip = socket.inet_ntoa(raw_ip_packet[12:16])
    dst_ip = socket.inet_ntoa(raw_ip_packet[16:20])
    transport = raw_ip_packet[ip_header_length:total_length]
    protocol = PROTOCOL_NAMES.get(protocol_number, f"PROTO-{protocol_number}")

    src_port = None
    dst_port = None
    tcp_flags = "-"

    if protocol == "TCP" and len(transport) >= 20:
        src_port, dst_port = struct.unpack("!HH", transport[:4])
        tcp_flags = tcp_flags_to_text(transport[13])
    elif protocol == "UDP" and len(transport) >= 8:
        src_port, dst_port = struct.unpack("!HH", transport[:4])
    elif protocol == "ICMP":
        tcp_flags = "-"

    return PacketRecord(
        packet_no=packet_no,
        timestamp=timestamp,
        src_ip=src_ip,
        dst_ip=dst_ip,
        protocol=protocol,
        src_port=src_port,
        dst_port=dst_port,
        packet_size=total_length or len(raw_ip_packet),
        tcp_flags=tcp_flags,
    )


def mark_classification(
    classes: list[str], reasons: list[str], index: int, label: str, reason: str
) -> None:
    if CLASS_PRIORITY[label] >= CLASS_PRIORITY[classes[index]]:
        classes[index] = label
        reasons[index] = reason


def detect_port_scans(
    packets: list[PacketRecord],
    classes: list[str],
    reasons: list[str],
    window_seconds: float,
    unique_port_threshold: int,
) -> None:
    by_src = defaultdict(list)
    for index, packet in enumerate(packets):
        if packet.dst_port is not None:
            by_src[packet.src_ip].append((index, packet))

    for src_ip, entries in by_src.items():
        left = 0
        for right in range(len(entries)):
            right_time = entries[right][1].timestamp
            while right_time - entries[left][1].timestamp > window_seconds:
                left += 1

            ports = {
                entry_packet.dst_port
                for _entry_index, entry_packet in entries[left : right + 1]
                if entry_packet.dst_port is not None
            }
            if len(ports) >= unique_port_threshold:
                for entry_index, entry_packet in entries[left : right + 1]:
                    mark_classification(
                        classes,
                        reasons,
                        entry_index,
                        "Port Scan Attack",
                        (
                            f"{src_ip} contacted {len(ports)} unique destination ports "
                            f"within {window_seconds:.1f} second(s)."
                        ),
                    )


def is_known_port(port: int | None) -> bool:
    if port is None:
        return False
    return port in KNOWN_PORTS or 10000 <= port <= 20000


def detect_suspicious_traffic(
    packets: list[PacketRecord],
    classes: list[str],
    reasons: list[str],
    window_seconds: float,
    packet_threshold: int,
) -> None:
    by_destination = defaultdict(list)
    for index, packet in enumerate(packets):
        if packet.dst_port is not None and not is_known_port(packet.dst_port):
            by_destination[(packet.dst_ip, packet.dst_port)].append((index, packet))

    for (dst_ip, dst_port), entries in by_destination.items():
        left = 0
        for right in range(len(entries)):
            right_time = entries[right][1].timestamp
            while right_time - entries[left][1].timestamp > window_seconds:
                left += 1

            count = right - left + 1
            if count >= packet_threshold:
                for entry_index, _packet in entries[left : right + 1]:
                    mark_classification(
                        classes,
                        reasons,
                        entry_index,
                        "Suspicious Traffic",
                        (
                            f"Unknown destination port {dst_port} on {dst_ip} "
                            f"received {count} packet(s) within {window_seconds:.1f} second(s)."
                        ),
                    )


def static_rule_match(packet: PacketRecord, blacklist: set[str]) -> tuple[str, str]:
    if packet.src_ip in blacklist:
        return "Malicious Traffic", "Source IP is present in the blacklist."

    if packet.protocol == "TCP" and packet.dst_port == 80:
        return "HTTP Traffic", "TCP destination port 80 matched the HTTP rule."
    if packet.protocol == "TCP" and packet.dst_port == 443:
        return "HTTPS Traffic", "TCP destination port 443 matched the HTTPS rule."
    if packet.protocol == "TCP" and packet.dst_port in {20, 21}:
        return "FTP Traffic", "TCP destination port 20/21 matched the FTP rule."
    if packet.protocol == "TCP" and packet.dst_port == 25:
        return "SMTP Traffic", "TCP destination port 25 matched the SMTP rule."
    if packet.protocol == "UDP" and packet.dst_port == 53:
        return "DNS Traffic", "UDP destination port 53 matched the DNS rule."
    if packet.protocol == "UDP" and (
        packet.dst_port == 5060 or (packet.dst_port is not None and 10000 <= packet.dst_port <= 20000)
    ):
        return "VoIP Traffic", "UDP destination port matched the VoIP rule."
    if packet.protocol == "ICMP":
        return "ICMP Traffic", "ICMP packets are tracked as control traffic."
    return "Unclassified Traffic", "No static rule matched this packet."


def classify_packets(
    packets: list[PacketRecord],
    blacklist: set[str] | None = None,
    port_scan_window: float = 1.0,
    port_scan_unique_ports: int = 5,
    suspicious_window: float = 1.0,
    suspicious_packet_threshold: int = 6,
) -> list[ClassifiedPacket]:
    blacklist = blacklist or {"203.0.113.250"}
    classes = ["Unclassified Traffic"] * len(packets)
    reasons = ["No rule evaluated yet."] * len(packets)

    for index, packet in enumerate(packets):
        label, reason = static_rule_match(packet, blacklist)
        classes[index] = label
        reasons[index] = reason

    detect_port_scans(
        packets, classes, reasons, port_scan_window, port_scan_unique_ports
    )
    detect_suspicious_traffic(
        packets, classes, reasons, suspicious_window, suspicious_packet_threshold
    )

    classified_packets = []
    for index, packet in enumerate(packets):
        if packet.src_ip in blacklist:
            mark_classification(
                classes,
                reasons,
                index,
                "Malicious Traffic",
                "Source IP is present in the blacklist.",
            )

        classified_packets.append(
            ClassifiedPacket(
                packet_no=packet.packet_no,
                timestamp=packet.timestamp,
                src_ip=packet.src_ip,
                dst_ip=packet.dst_ip,
                protocol=packet.protocol,
                src_port=packet.src_port,
                dst_port=packet.dst_port,
                packet_size=packet.packet_size,
                tcp_flags=packet.tcp_flags,
                traffic_class=classes[index],
                reason=reasons[index],
            )
        )

    return classified_packets


def print_packet_table(packets: list[ClassifiedPacket], limit: int) -> None:
    if not packets:
        print("No supported IPv4 packets were found in the capture.")
        return

    header = (
        f"{'No':<4}{'Time':<10}{'Source':<18}{'Destination':<18}"
        f"{'Proto':<7}{'SPort':<8}{'DPort':<8}{'Size':<7}"
        f"{'Flags':<14}{'Class'}"
    )
    print(header)
    print("-" * len(header))

    for packet in packets[:limit]:
        src_port = packet.src_port if packet.src_port is not None else "-"
        dst_port = packet.dst_port if packet.dst_port is not None else "-"
        print(
            f"{packet.packet_no:<4}{packet.timestamp:<10.3f}{packet.src_ip:<18}"
            f"{packet.dst_ip:<18}{packet.protocol:<7}{str(src_port):<8}"
            f"{str(dst_port):<8}{packet.packet_size:<7}{packet.tcp_flags:<14}"
            f"{packet.traffic_class}"
        )

    if len(packets) > limit:
        remaining = len(packets) - limit
        print(f"\n... {remaining} more packet(s) not shown in the preview.")


def print_summary(packets: list[ClassifiedPacket]) -> None:
    counts = Counter(packet.traffic_class for packet in packets)

    print("\nTraffic Summary")
    print("-" * 40)
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{label:<22} : {count}")


def write_json_report(output_path: Path, packets: list[ClassifiedPacket]) -> None:
    payload = [asdict(packet) for packet in packets]
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Static packet classification using pcap header fields and rule-based logic."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to the input .pcap file.",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=25,
        help="Number of packet rows to print in the preview table.",
    )
    parser.add_argument(
        "-j",
        "--json-output",
        type=Path,
        help="Optional path to save the classified packets as JSON.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        packets = read_pcap_packets(args.input)
        classified_packets = classify_packets(packets)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print_packet_table(classified_packets, max(args.limit, 1))
    print_summary(classified_packets)

    if args.json_output is not None:
        write_json_report(args.json_output, classified_packets)
        print(f"\nJSON report written to: {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
