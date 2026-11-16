#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Write a test report for the registry, filling in what this Mac can tell about itself.

    make_report.py KEXT_ID VERSION RESULT [--asset NAME] [--device 8086:2725 ...]
                   [--feature wifi=works ...] [--notes TEXT] [--bootloader "OpenCore 1.0.8"]
                   [--login YOUR_GITHUB_LOGIN] [--write]

RESULT is works, partial or broken. Without --write the report is printed; with --write
(and --login) it is saved to kexts/<id>/reports/<login>/<version>-<build>.toml and checked.

Collected from the system: macOS version and build (sw_vers), CPU name and SMBIOS model
(sysctl). Nothing else: no serial numbers, MAC addresses or network names. Read the
result before you send it. Standard library only; runs on macOS.
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from openkext_registry import model  # noqa: E402


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def render(a, mac_version, build, cpu, smbios):
    lines = [f"kext = {q(a.kext)}", f"version = {q(a.version)}"]
    if a.asset:
        lines.append(f"asset = {q(a.asset)}")
    lines += [f"result = {q(a.result)}", f"date = {dt.date.today().isoformat()}"]
    if a.notes:
        lines.append(f"notes = {q(a.notes)}")
    lines += ["", "[macos]", f"version = {q(mac_version)}", f"build = {q(build)}",
              "", "[hardware]", f"cpu = {q(cpu)}", f"smbios = {q(smbios)}"]
    if a.bootloader:
        lines.append(f"bootloader = {q(a.bootloader)}")
    if a.device:
        lines.append("device_ids = [" + ", ".join(q(d.lower()) for d in a.device) + "]")
    if a.feature:
        lines += ["", "[features]"]
        for f in a.feature:
            name, _, state = f.partition("=")
            lines.append(f"{name} = {q(state)}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write an OpenKext test report from this Mac.")
    ap.add_argument("kext")
    ap.add_argument("version")
    ap.add_argument("result", choices=sorted(model.RESULTS))
    ap.add_argument("--asset")
    ap.add_argument("--device", action="append", default=[], help="vendor:device id, e.g. 8086:2725")
    ap.add_argument("--feature", action="append", default=[], help="name=works|partial|broken|untested")
    ap.add_argument("--notes")
    ap.add_argument("--bootloader")
    ap.add_argument("--login", help="your GitHub login (needed with --write)")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)

    mac_version = run("sw_vers", "-productVersion")
    build = run("sw_vers", "-buildVersion")
    cpu = run("sysctl", "-n", "machdep.cpu.brand_string") or run("sysctl", "-n", "hw.model")
    smbios = run("sysctl", "-n", "hw.model")
    cpu = re.sub(r"\s+", " ", cpu)[:80]
    text = render(a, mac_version, build, cpu, smbios)

    entry_path = os.path.join(ROOT, "kexts", a.kext, "kext.toml")
    if not os.path.isfile(entry_path):
        sys.exit(f"{a.kext} is not in the registry (no {entry_path})")
    with open(entry_path, "rb") as f:
        entry, _ = model.parse_toml(f.read())
    report, err = model.parse_toml(text.encode())
    errors = [err] if err else model.check_report(report, entry)

    if not a.write:
        sys.stdout.write(text)
    else:
        if not a.login or not model.LOGIN_RE.match(a.login):
            sys.exit("--write needs --login with your GitHub login")
        name = f"{a.version}-{build}".lower().replace("+", "-") + ".toml"
        path = os.path.join(ROOT, "kexts", a.kext, "reports", a.login, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
