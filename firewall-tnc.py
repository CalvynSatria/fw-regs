"""
Firewall TNC Tester (final logic)

Decision matrix (Destination cell vs Destination Name cell):
  Dest = Single IP, Name = anything              -> TESTED pakai Single IP
  Dest = IP Range,  Name = valid FQDN            -> TESTED pakai FQDN
  Dest = IP Range,  Name = absurd / empty        -> UNTESTED (skip)
  Dest = Hostname,  Name = IP                    -> TESTED pakai IP di Name
  Dest = Hostname,  Name = valid FQDN            -> TESTED pakai FQDN
  Dest = Hostname,  Name = absurd / empty        -> TESTED pakai hostname Dest
  Dest = empty,     Name = anything usable       -> TESTED pakai Name
  Dest = empty,     Name = absurd                -> UNTESTED

"Valid FQDN"  = contains at least one dot, no spaces
"Absurd name" = no dot, atau kosong, atau cuma spasi

Header Excel auto-detect (cari baris yang mengandung "Source IP").
"""

import os
import re
import sys
import subprocess
from datetime import datetime

import pandas as pd
from tabulate import tabulate


# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------
SERVICE_NAME_MAP = {
    "http": 80, "https": 443, "ssh": 22, "ftp": 21, "ftps": 990, "sftp": 22,
    "smtp": 25, "smtps": 465, "submission": 587,
    "pop3": 110, "pop3s": 995, "imap": 143, "imaps": 993,
    "dns": 53, "rdp": 3389, "smb": 445, "cifs": 445,
    "mysql": 3306, "mssql": 1433, "postgresql": 5432, "postgres": 5432,
    "ldap": 389, "ldaps": 636, "ntp": 123, "telnet": 23,
    "snmp": 161, "snmptrap": 162, "syslog": 514, "vnc": 5900,
    "mqtt": 1883, "mqtts": 8883, "redis": 6379, "mongodb": 27017,
    "kafka": 9092, "elasticsearch": 9200, "kibana": 5601,
    "winrm": 5985, "winrm-https": 5986, "wsus": 8530, "wsus-https": 8531,
}

RE_IPV4 = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
RE_CIDR = re.compile(r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$")
RE_DIGIT = re.compile(r"\d+")


# -------------------------------------------------------------------
# Parsers
# -------------------------------------------------------------------
def parse_service(value):
    """Extract port dari cell Service. Return int (0 kalau gak ke-parse)."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        p = int(value)
        return p if 0 < p < 65536 else 0

    s = str(value).strip()
    if not s:
        return 0

    key = s.lower().replace(" ", "")
    if key in SERVICE_NAME_MAP:
        return SERVICE_NAME_MAP[key]

    m = RE_DIGIT.search(s)
    if m:
        port = int(m.group(0))
        if 0 < port < 65536:
            return port

    return 0


def _normalize_value(value):
    """Normalize cell: replace newline dengan koma, rapihin spasi."""
    if value is None:
        return []
    s = str(value).replace("\n", ",").replace("\r", ",")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return parts


def parse_destination(value):
    """Return (target_for_log, type_label).
    type_label: 'IP' | 'CIDR' | 'CIDR_LIST' | 'IP_LIST' | 'NAME' | 'WEIRD' | 'EMPTY'
    """
    parts = _normalize_value(value)
    if not parts:
        return ("", "EMPTY")

    if len(parts) == 1:
        s = parts[0]
        if RE_IPV4.match(s):
            return (s, "IP")
        if RE_CIDR.match(s):
            return (s, "CIDR")
        if "/" in s and RE_DIGIT.search(s):
            return (s, "WEIRD")
        return (s, "NAME")

    # Multi-value
    if all(RE_IPV4.match(p) for p in parts):
        return (parts[0], "IP_LIST")
    if all(RE_CIDR.match(p) for p in parts):
        return (parts[0], "CIDR_LIST")
    return (parts[0], "MULTI")


def is_valid_fqdn(name):
    """Name valid = ada minimal 1 dot, gak ada spasi, gak kosong."""
    if not name:
        return False
    s = str(name).strip()
    if not s or " " in s:
        return False
    return "." in s


def resolve_target(dest_raw, dest_name):
    """
    Decide target tnc. Return: (target_str, status, reason, dest_type)
      status:  'TESTED' | 'UNTESTED'
      reason:  string penjelas (untuk log & kolom Reason di Excel)
    """
    target, dest_type = parse_destination(dest_raw)
    name_clean = (str(dest_name).strip() if dest_name is not None else "")
    name_valid = is_valid_fqdn(name_clean)
    name_is_ip = bool(RE_IPV4.match(name_clean))

    # === CASE 1: Destination = Single IP ===
    if dest_type == "IP":
        if not name_valid and not name_is_ip and name_clean:
            reason = f"single IP, name '{name_clean}' absurd (diabaikan)"
        elif name_valid or name_is_ip:
            reason = f"single IP, name column diabaikan"
        else:
            reason = "single IP"
        return (target, "TESTED", reason, dest_type)

    # === CASE 2: Destination = Range (CIDR / IP_LIST / CIDR_LIST / MULTI) ===
    if dest_type in ("CIDR", "IP_LIST", "CIDR_LIST", "MULTI"):
        if name_valid:
            return (name_clean, "TESTED", f"{dest_type} -> pakai FQDN dari Name", dest_type)
        # name absurd / kosong
        if name_clean and not name_valid:
            return ("", "UNTESTED",
                    f"{dest_type} + name '{name_clean}' absurd (no dot) -> skip", dest_type)
        return ("", "UNTESTED",
                f"{dest_type} + name kosong -> skip", dest_type)

    # === CASE 3: Destination = Hostname / TAG (NAME type) ===
    if dest_type == "NAME":
        # Name column is single IP (kemungkinan data ke-swap)
        if name_is_ip:
            return (name_clean, "TESTED",
                    f"dest hostname '{target}', name column has IP -> pakai IP", dest_type)
        # Name column is valid FQDN
        if name_valid:
            return (name_clean, "TESTED",
                    f"dest hostname, name has FQDN -> pakai FQDN", dest_type)
        # Name absurd / kosong -> pakai destination hostname
        if target:
            return (target, "TESTED",
                    f"dest hostname '{target}' dipakai, name '{name_clean}' absurd/kosong", dest_type)
        return ("", "UNTESTED", "dest NAME kosong & name kosong", dest_type)

    # === CASE 4: Destination = WEIRD ===
    if dest_type == "WEIRD":
        if name_valid or name_is_ip:
            return (name_clean, "TESTED",
                    f"dest WEIRD '{target}', pakai name column", dest_type)
        return (target, "TESTED",
                f"dest WEIRD '{target}', name kosong/absurd, coba pakai dest seadanya", dest_type)

    # === CASE 5: Destination = EMPTY ===
    if dest_type == "EMPTY":
        if name_is_ip:
            return (name_clean, "TESTED", "dest kosong, name has IP", dest_type)
        if name_valid:
            return (name_clean, "TESTED", "dest kosong, pakai name FQDN", dest_type)
        return ("", "UNTESTED", "dest kosong & name kosong/absurd", dest_type)

    # Fallback (shouldn't reach)
    return (target, "TESTED", "fallback", dest_type)


# -------------------------------------------------------------------
# Path resolver
# -------------------------------------------------------------------
def find_project_root(start_dir, marker="source_excel", max_up=3):
    current = os.path.abspath(start_dir)
    for _ in range(max_up + 1):
        if os.path.isdir(os.path.join(current, marker)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(start_dir)


if getattr(sys, "frozen", False):
    START_DIR = os.path.dirname(sys.executable)
else:
    START_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = find_project_root(START_DIR, marker="source_excel", max_up=3)
SOURCE_DIR = os.path.join(BASE_DIR, "source_excel")
RESULT_DIR = os.path.join(BASE_DIR, "result")
os.makedirs(RESULT_DIR, exist_ok=True)


# -------------------------------------------------------------------
# TNC runner
# -------------------------------------------------------------------
def run_tnc(destination, port, timeout=600):
    if port and port > 0:
        cmd = f"tnc {destination} -p {port}"
    else:
        cmd = f"tnc {destination}"
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.stdout


def parse_tnc_result(output):
    ping_result = "Unknown"
    tcp_result = "Unknown"
    for line in output.splitlines():
        if "PingSucceeded" in line:
            ping_result = line.split(":", 1)[-1].strip()
        elif "TcpTestSucceeded" in line:
            tcp_result = line.split(":", 1)[-1].strip()
    return ping_result, tcp_result


def find_input_file():
    if not os.path.isdir(SOURCE_DIR):
        raise FileNotFoundError(
            f"Folder input gak ketemu.\n  Dicari: {SOURCE_DIR}\n  BASE_DIR: {BASE_DIR}"
        )
    xlsx_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(".xlsx")]
    if not xlsx_files:
        raise FileNotFoundError(f"Tidak ada file .xlsx di {SOURCE_DIR}.")
    xlsx_files.sort(
        key=lambda f: os.path.getmtime(os.path.join(SOURCE_DIR, f)),
        reverse=True,
    )
    return os.path.join(SOURCE_DIR, xlsx_files[0])


def read_excel_smart(path):
    """Auto-detect header row (cari yang ada 'Source IP' di salah satu cell)."""
    raw = pd.read_excel(path, header=None)
    header_row = 0
    for i, row in raw.iterrows():
        if any(isinstance(v, str) and "Source IP" in v for v in row.values):
            header_row = i
            break
    print(f"[INFO] Header row detected at index {header_row} "
          f"-> {list(raw.iloc[header_row].values)}")
    return pd.read_excel(path, header=header_row)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
def main():
    print(f"[INFO] Base dir : {BASE_DIR}")
    print(f"[INFO] Source   : {SOURCE_DIR}")
    print(f"[INFO] Result   : {RESULT_DIR}")
    print()

    input_path = find_input_file()
    print(f"[INFO] Input    : {input_path}")
    firewall_log = read_excel_smart(input_path)
    print(f"[INFO] Rows     : {len(firewall_log)}")
    print()

    required_cols = ["Source IP / TAG / Group", "Destination IP /TAG / Group", "Service"]
    missing = [c for c in required_cols if c not in firewall_log.columns]
    if missing:
        raise ValueError(f"Kolom wajib hilang di Excel: {missing}\n"
                         f"Kolom yang ada: {list(firewall_log.columns)}")

    has_name_col = "Destination Name" in firewall_log.columns
    if has_name_col:
        print("[INFO] Kolom 'Destination Name' terdeteksi")
    else:
        print("[WARN] Kolom 'Destination Name' TIDAK ada")
    print()

    results = []
    total = len(firewall_log)

    for idx, row in firewall_log.iterrows():
        dest_raw = row.get("Destination IP /TAG / Group", "")
        svc_raw = row.get("Service", "")
        src_raw = row.get("Source IP / TAG / Group", "")
        src_name_raw = row.get("Source Name", "")
        dest_name_raw = row.get("Destination Name", "") if has_name_col else ""

        port = parse_service(svc_raw)
        target, status, reason, dest_type = resolve_target(dest_raw, dest_name_raw)

        # === Build log line ===
        if status == "UNTESTED":
            print(f"[{idx + 1}/{total}] SKIP | {reason}")
            results.append(_row_result(
                src_raw, src_name_raw, dest_raw, dest_name_raw, dest_type,
                svc_raw, target, status, reason, "UNTESTED", "UNTESTED",
            ))
            continue

        # Warn on edge cases
        if dest_type == "WEIRD":
            print(f"[{idx + 1}/{total}] WARN — destination '{dest_raw}' format aneh, "
                  f"mungkin salah kolom")
        if port == 0 and svc_raw not in (None, "", 0):
            print(f"[{idx + 1}/{total}] WARN — service '{svc_raw}' gak ke-parse jadi port, "
                  f"lanjut tanpa -p (ping only)")

        # Print tnc call
        if port > 0:
            tnc_call = f"tnc {target} -p {port}"
        else:
            tnc_call = f"tnc {target}  (ping only)"
        print(f"[{idx + 1}/{total}] [{dest_type}] -> {tnc_call}")
        print(f"           reason: {reason}")

        # Run test
        try:
            output = run_tnc(target, port)
            ping_status, tcp_status = parse_tnc_result(output)
            print(f"           ping={ping_status} tcp={tcp_status}")
        except subprocess.TimeoutExpired:
            ping_status, tcp_status = "Timeout", "Timeout"
            print("           TIMEOUT")
        except Exception as e:
            ping_status, tcp_status = f"Error: {e}", f"Error: {e}"
            print(f"           ERROR ({e})")

        results.append(_row_result(
            src_raw, src_name_raw, dest_raw, dest_name_raw, dest_type,
            svc_raw, target, status, reason, ping_status, tcp_status,
        ))

    result_df = pd.DataFrame(results)
    print()
    print(tabulate(result_df, headers="keys", tablefmt="grid"))

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(RESULT_DIR, f"result-firewall-{timestamp}.xlsx")
    result_df.to_excel(filename, index=False)
    print(f"\n[SAVED] {filename}")


def _row_result(src, src_name, dest, dest_name, dest_type, svc,
                tested_target, status, reason, ping, tcp):
    return {
        "Source IP / TAG / Group": str(src),
        "Source Name": str(src_name) if src_name else "",
        "Destination IP (raw)": str(dest),
        "Destination Name (raw)": str(dest_name) if dest_name else "",
        "Destination Type": dest_type,
        "Service (raw)": str(svc),
        "Tested Target": str(tested_target) if tested_target else "(skipped)",
        "Status": status,
        "Reason": reason,
        "PingSucceeded": ping,
        "TcpTestSucceeded": tcp,
    }


if __name__ == "__main__":
    main()
