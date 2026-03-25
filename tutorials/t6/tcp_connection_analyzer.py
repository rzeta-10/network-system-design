#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


ConnectionKey = Tuple[str, int, str, int]


TCP_LINE_RE = re.compile(
    r"\bIP6?\s+(?P<src>\S+)\s+>\s+(?P<dst>.+?):\s+Flags\s+\[(?P<flags>[^\]]+)\]"
)
ENDPOINT_RE = re.compile(r"(?P<ip>.+)\.(?P<port>\d+)$")

PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1",  # pcap (little endian)
    b"\xa1\xb2\xc3\xd4",  # pcap (big endian)
    b"\x4d\x3c\xb2\xa1",  # pcap-ns (little endian)
    b"\xa1\xb2\x3c\x4d",  # pcap-ns (big endian)
    b"\x0a\x0d\x0d\x0a",  # pcapng
}


@dataclass
class ConnectionStats:
    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    syn_count: int = 0
    syn_ack_count: int = 0
    ack_count: int = 0
    saw_syn: bool = False
    saw_syn_ack: bool = False
    saw_final_ack: bool = False

    def handshake_status(self) -> str:
        if self.saw_syn and self.saw_syn_ack and self.saw_final_ack:
            return "COMPLETED"
        return "FAILED/INCOMPLETE"


def is_pcap_file(file_path: Path) -> bool:
    try:
        with file_path.open("rb") as f:
            return f.read(4) in PCAP_MAGICS
    except OSError:
        return False


def read_trace_lines(input_path: Path) -> Iterable[str]:
    if is_pcap_file(input_path):
        if shutil.which("tcpdump") is None:
            raise RuntimeError(
                "Input appears to be pcap/pcapng but 'tcpdump' is not installed."
            )
        cmd = ["tcpdump", "-nn", "-tt", "-r", str(input_path), "tcp"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "unknown error"
            raise RuntimeError(f"tcpdump failed to read pcap: {stderr}")
        return proc.stdout.splitlines()

    with input_path.open("r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def parse_endpoint(endpoint: str) -> Optional[Tuple[str, int]]:
    match = ENDPOINT_RE.match(endpoint)
    if not match:
        return None
    return match.group("ip"), int(match.group("port"))


def parse_line(line: str) -> Optional[Tuple[str, int, str, int, str]]:
    match = TCP_LINE_RE.search(line)
    if not match:
        return None

    src = parse_endpoint(match.group("src"))
    dst = parse_endpoint(match.group("dst"))
    if not src or not dst:
        return None

    flags = match.group("flags")
    return src[0], src[1], dst[0], dst[1], flags


def has_ack_flag(flags: str) -> bool:
    # tcpdump typically represents ACK as '.'; some tools may show 'A'.
    return "." in flags or "A" in flags


def make_stats_from_key(key: ConnectionKey) -> ConnectionStats:
    return ConnectionStats(
        source_ip=key[0],
        source_port=key[1],
        destination_ip=key[2],
        destination_port=key[3],
    )


def analyze_trace(lines: Iterable[str]) -> Dict[ConnectionKey, ConnectionStats]:
    connections: Dict[ConnectionKey, ConnectionStats] = {}

    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            continue

        src_ip, src_port, dst_ip, dst_port, flags = parsed
        syn = "S" in flags
        ack = has_ack_flag(flags)

        if syn and not ack:
            key = (src_ip, src_port, dst_ip, dst_port)
            stats = connections.setdefault(key, make_stats_from_key(key))
            stats.syn_count += 1
            stats.saw_syn = True
            continue

        if syn and ack:
            # SYN-ACK belongs to reverse of initial SYN direction.
            key = (dst_ip, dst_port, src_ip, src_port)
            stats = connections.setdefault(key, make_stats_from_key(key))
            stats.syn_ack_count += 1
            stats.saw_syn_ack = True
            continue

        if ack and not syn:
            direct_key = (src_ip, src_port, dst_ip, dst_port)
            reverse_key = (dst_ip, dst_port, src_ip, src_port)

            from_client_direction = True
            if direct_key in connections:
                key = direct_key
            elif reverse_key in connections:
                key = reverse_key
                from_client_direction = False
            else:
                key = direct_key
                connections[key] = make_stats_from_key(key)

            stats = connections[key]
            stats.ack_count += 1

            if from_client_direction and stats.saw_syn and stats.saw_syn_ack:
                stats.saw_final_ack = True

    return connections


def print_table(connections: Dict[ConnectionKey, ConnectionStats]) -> None:
    if not connections:
        print("No TCP connections parsed from input.")
        return

    header = (
        f"{'Connection (src:port -> dst:port)':55}"
        f"{'SYN':>8}{'SYN-ACK':>10}{'ACK':>8}{'Handshake':>22}"
    )
    print(header)
    print("-" * len(header))

    for key in sorted(connections):
        stats = connections[key]
        conn_label = (
            f"{stats.source_ip}:{stats.source_port} -> "
            f"{stats.destination_ip}:{stats.destination_port}"
        )
        print(
            f"{conn_label:55}"
            f"{stats.syn_count:>8}{stats.syn_ack_count:>10}{stats.ack_count:>8}"
            f"{stats.handshake_status():>22}"
        )


def write_json_output(
    output_path: Path, connections: Dict[ConnectionKey, ConnectionStats]
) -> None:
    payload = []
    for key in sorted(connections):
        stats = connections[key]
        entry = asdict(stats)
        entry["handshake_status"] = stats.handshake_status()
        payload.append(entry)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze TCP connection handshake behavior from tcpdump traces."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=Path,
        help="Path to trace input (.pcap/.pcapng or tcpdump text output).",
    )
    parser.add_argument(
        "-j",
        "--json-output",
        type=Path,
        help="Optional path to save results in JSON format.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 1

    try:
        lines = read_trace_lines(args.input)
        connections = analyze_trace(lines)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print_table(connections)

    if args.json_output is not None:
        write_json_output(args.json_output, connections)
        print(f"\nJSON report written to: {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
