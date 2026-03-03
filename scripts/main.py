#!/usr/bin/env python3
"""
Cisco Interface Health Check — IAG Python Service

Connects to a Cisco device via Netmiko, runs 'show interface' for each
specified interface, and returns a JSON report with status, speed, and
error counters.

Inputs (via IAG decorator):
  --device_ip       Target device IP
  --device_type     Netmiko device type (default: cisco_ios)
  --interfaces      Comma-separated interface names (e.g. "GigabitEthernet0/1,Loopback0")

Credentials (via IAG secrets → env vars):
  DEVICE_USERNAME   SSH username
  DEVICE_PASSWORD   SSH password
"""

import argparse
import json
import os
import re
import sys

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException


def parse_interface_output(raw: str) -> dict:
    """Extract status, speed, and error counters from 'show interface' output."""
    info = {
        "raw_status": None,
        "line_protocol": None,
        "speed": None,
        "mtu": None,
        "input_errors": 0,
        "output_errors": 0,
        "crc_errors": 0,
        "input_packets": 0,
        "output_packets": 0,
    }

    # Line 1: "GigabitEthernet0/1 is up, line protocol is up"
    m = re.search(r"is (administratively )?(up|down), line protocol is (up|down)", raw)
    if m:
        info["raw_status"] = "admin-down" if m.group(1) else m.group(2)
        info["line_protocol"] = m.group(3)

    # Speed: "BW 1000000 Kbit/sec" or "100Mb/s"
    m = re.search(r"BW (\d+) Kbit", raw)
    if m:
        kbit = int(m.group(1))
        if kbit >= 1_000_000:
            info["speed"] = f"{kbit // 1_000_000} Gbps"
        elif kbit >= 1_000:
            info["speed"] = f"{kbit // 1_000} Mbps"
        else:
            info["speed"] = f"{kbit} Kbps"

    # MTU
    m = re.search(r"MTU (\d+) bytes", raw)
    if m:
        info["mtu"] = int(m.group(1))

    # Input errors: "X input errors, Y CRC, ..."
    m = re.search(r"(\d+) input errors", raw)
    if m:
        info["input_errors"] = int(m.group(1))

    m = re.search(r"(\d+) CRC", raw)
    if m:
        info["crc_errors"] = int(m.group(1))

    # Output errors
    m = re.search(r"(\d+) output errors", raw)
    if m:
        info["output_errors"] = int(m.group(1))

    # Packet counters
    m = re.search(r"(\d+) packets input", raw)
    if m:
        info["input_packets"] = int(m.group(1))

    m = re.search(r"(\d+) packets output", raw)
    if m:
        info["output_packets"] = int(m.group(1))

    return info


def main():
    parser = argparse.ArgumentParser(description="Cisco Interface Health Check")
    parser.add_argument("--device_ip", required=True, help="Target device IP")
    parser.add_argument("--device_type", default="cisco_ios", help="Netmiko device type")
    parser.add_argument("--interfaces", required=True, help="Comma-separated interface names")
    parser.add_argument("--debug", default="false", help="Set to 'true' to include raw output")
    args = parser.parse_args()

    username = os.environ.get("DEVICE_USERNAME")
    password = os.environ.get("DEVICE_PASSWORD")
    if not username or not password:
        print(json.dumps({"success": False, "error": "DEVICE_USERNAME and DEVICE_PASSWORD env vars required"}))
        sys.exit(1)

    interfaces = [i.strip() for i in args.interfaces.split(",") if i.strip()]
    if not interfaces:
        print(json.dumps({"success": False, "error": "No interfaces specified"}))
        sys.exit(1)

    report = {
        "success": True,
        "device_ip": args.device_ip,
        "device_type": args.device_type,
        "interfaces": {},
        "summary": {
            "total": len(interfaces),
            "up": 0,
            "down": 0,
            "admin_down": 0,
            "errors_detected": 0,
        },
    }

    try:
        device = {
            "device_type": args.device_type,
            "host": args.device_ip,
            "username": username,
            "password": password,
            "timeout": 30,
        }
        conn = ConnectHandler(**device)

        for intf in interfaces:
            cmd = f"show interface {intf}"
            output = conn.send_command_timing(cmd, read_timeout=30)
            parsed = parse_interface_output(output)

            has_errors = (parsed["input_errors"] + parsed["output_errors"] + parsed["crc_errors"]) > 0
            intf_entry = {
                "status": parsed["raw_status"],
                "line_protocol": parsed["line_protocol"],
                "speed": parsed["speed"],
                "mtu": parsed["mtu"],
                "counters": {
                    "input_packets": parsed["input_packets"],
                    "output_packets": parsed["output_packets"],
                    "input_errors": parsed["input_errors"],
                    "output_errors": parsed["output_errors"],
                    "crc_errors": parsed["crc_errors"],
                },
                "has_errors": has_errors,
            }
            if args.debug.lower() == "true":
                intf_entry["raw_output"] = output
            report["interfaces"][intf] = intf_entry

            if parsed["raw_status"] == "up":
                report["summary"]["up"] += 1
            elif parsed["raw_status"] == "admin-down":
                report["summary"]["admin_down"] += 1
            else:
                report["summary"]["down"] += 1

            if has_errors:
                report["summary"]["errors_detected"] += 1

        conn.disconnect()

    except NetmikoTimeoutException:
        report["success"] = False
        report["error"] = f"Connection timed out to {args.device_ip}"
    except NetmikoAuthenticationException:
        report["success"] = False
        report["error"] = f"Authentication failed for {args.device_ip}"
    except Exception as e:
        report["success"] = False
        report["error"] = str(e)

    print(json.dumps(report))


if __name__ == "__main__":
    main()
