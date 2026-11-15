# SPDX-License-Identifier: MIT
"""Entry and report files: parsing and schema checks. Standard library only."""
import datetime as _dt
import re
import tomllib

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
REPORT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,80}\.toml$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,40}$")
MACOS_RE = re.compile(r"^(1[0-9]|2[0-9])(\.[0-9]{1,2}){1,2}$")
BUILD_RE = re.compile(r"^[0-9]{2}[A-Z][0-9]{1,4}[a-z]?$")
GITHUB_REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)$")
HW_ID_RE = re.compile(r"^[0-9a-f]{4}:[0-9a-f]{4}$")

KINDS = {"kext", "patch", "tool", "docs"}
CATEGORIES = {"wifi", "bluetooth", "audio", "graphics", "ethernet", "usb", "storage",
              "input", "power", "sensors", "cpu", "firmware", "other"}
RESULTS = {"works", "partial", "broken"}
FEATURE_STATES = {"works", "partial", "broken", "untested"}

# Licenses accepted without review, and phrases that must all appear in the license file
# (case and whitespace are ignored). Anything else goes to manual review.
LICENSES = {
    "GPL-2.0-only": ["GNU GENERAL PUBLIC LICENSE", "Version 2, June 1991"],
    "GPL-2.0-or-later": ["GNU GENERAL PUBLIC LICENSE", "Version 2, June 1991"],
    "GPL-3.0-only": ["GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007"],
    "GPL-3.0-or-later": ["GNU GENERAL PUBLIC LICENSE", "Version 3, 29 June 2007"],
    "LGPL-2.1-only": ["GNU LESSER GENERAL PUBLIC LICENSE", "Version 2.1"],
    "LGPL-2.1-or-later": ["GNU LESSER GENERAL PUBLIC LICENSE", "Version 2.1"],
    "MIT": ["Permission is hereby granted, free of charge"],
    "BSD-2-Clause": ["Redistribution and use in source and binary forms"],
    "BSD-3-Clause": ["Redistribution and use in source and binary forms", "Neither the name"],
    "ISC": ["Permission to use, copy, modify, and"],
    "Apache-2.0": ["Apache License", "Version 2.0, January 2004"],
    "MPL-2.0": ["Mozilla Public License Version 2.0"],
    "APSL-2.0": ["APPLE PUBLIC SOURCE LICENSE", "Version 2.0"],
}


def normalize(text):
    return " ".join(text.split()).lower()


def license_text_matches(spdx, text):
    phrases = LICENSES.get(spdx)
    if not phrases:
        return False
    body = normalize(text)
    return all(normalize(p) in body for p in phrases)


def parse_toml(data):
    """Bytes -> (dict or None, error or None)."""
    try:
        return tomllib.loads(data.decode("utf-8")), None
    except UnicodeDecodeError:
        return None, "not UTF-8 text"
    except tomllib.TOMLDecodeError as e:
        return None, f"TOML error: {e}"


def _str(d, key, errors, required=True, maxlen=200, pattern=None):
    v = d.get(key)
    if v is None:
        if required:
            errors.append(f"`{key}` is required")
        return None
    if not isinstance(v, str) or not v.strip():
        errors.append(f"`{key}` must be a non-empty string")
        return None
    if len(v) > maxlen:
        errors.append(f"`{key}` is longer than {maxlen} characters")
    if pattern and not pattern.match(v):
        errors.append(f"`{key}` has an invalid value: {v!r}")
    return v


def _list_of_str(d, key, errors, required=True, pattern=None, allowed=None, maxitems=20):
    v = d.get(key)
    if v is None:
        if required:
            errors.append(f"`{key}` is required")
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        errors.append(f"`{key}` must be a list of strings")
        return []
    if required and not v:
        errors.append(f"`{key}` must not be empty")
    if len(v) > maxitems:
        errors.append(f"`{key}` has more than {maxitems} items")
    for x in v:
        if pattern and not pattern.match(x):
            errors.append(f"`{key}` has an invalid item: {x!r}")
        if allowed and x not in allowed:
            errors.append(f"`{key}` item {x!r} is not one of: {', '.join(sorted(allowed))}")
    if len(set(v)) != len(v):
        errors.append(f"`{key}` has duplicates")
    return v


def _version_key(v):
    return tuple(int(x) for x in v.split("."))


KEXT_KEYS = {"id", "name", "summary", "kind", "categories", "source", "license", "license_file",
             "maintainers", "ai_disclosure", "homepage", "based_on", "hardware", "macos", "releases"}


def check_kext(d, dir_id):
    """Schema check of a kext.toml dict. Returns a list of errors (empty when valid)."""
    errors = []
    unknown = set(d) - KEXT_KEYS
    if unknown:
        errors.append(f"unknown keys: {', '.join(sorted(unknown))}")
    kid = _str(d, "id", errors, pattern=ID_RE, maxlen=50)
    if kid and kid != dir_id:
        errors.append(f"`id` ({kid}) must match the directory name ({dir_id})")
    _str(d, "name", errors, maxlen=80)
    _str(d, "summary", errors, maxlen=280)
    kind = _str(d, "kind", errors, maxlen=10)
    if kind and kind not in KINDS:
        errors.append(f"`kind` must be one of: {', '.join(sorted(KINDS))}")
    _list_of_str(d, "categories", errors, allowed=CATEGORIES, maxitems=5)
    _str(d, "source", errors, pattern=GITHUB_REPO_RE, maxlen=150)
    lic = _str(d, "license", errors, maxlen=40)
    if lic and lic not in LICENSES:
        errors.append(f"REVIEW: license {lic!r} is not on the automatic list ({', '.join(sorted(LICENSES))})")
    lf = _str(d, "license_file", errors, required=False, maxlen=200)
    if lf and (lf.startswith("/") or ".." in lf.split("/")):
        errors.append("`license_file` must be a relative path inside the repository")
    _list_of_str(d, "maintainers", errors, pattern=LOGIN_RE, maxitems=10)
    _str(d, "ai_disclosure", errors, maxlen=280)
    _str(d, "homepage", errors, required=False, maxlen=200, pattern=re.compile(r"^https://"))
    _list_of_str(d, "based_on", errors, required=False, pattern=re.compile(r"^https://"), maxitems=20)

    hw = d.get("hardware", [])
    if not isinstance(hw, list):
        errors.append("`hardware` must be a list of tables ([[hardware]])")
        hw = []
    for i, h in enumerate(hw):
        if not isinstance(h, dict):
            errors.append(f"hardware[{i}] must be a table")
            continue
        extra = set(h) - {"vendor", "description", "pci_ids", "usb_ids"}
        if extra:
            errors.append(f"hardware[{i}]: unknown keys: {', '.join(sorted(extra))}")
        _str(h, "vendor", errors, maxlen=40)
        _str(h, "description", errors, maxlen=120)
        _list_of_str(h, "pci_ids", errors, required=False, pattern=HW_ID_RE, maxitems=64)
        _list_of_str(h, "usb_ids", errors, required=False, pattern=HW_ID_RE, maxitems=64)

    mac = d.get("macos")
    if not isinstance(mac, dict):
        errors.append("`[macos]` with `min` and `max` is required")
    else:
        lo = _str(mac, "min", errors, pattern=MACOS_RE, maxlen=8)
        hi = _str(mac, "max", errors, pattern=MACOS_RE, maxlen=8)
        if lo and hi and MACOS_RE.match(lo) and MACOS_RE.match(hi) and _version_key(lo) > _version_key(hi):
            errors.append("`macos.min` is newer than `macos.max`")

    rel = d.get("releases")
    if not isinstance(rel, list) or not rel:
        errors.append("at least one `[[releases]]` entry is required")
        rel = []
    seen = set()
    for i, r in enumerate(rel):
        if not isinstance(r, dict):
            errors.append(f"releases[{i}] must be a table")
            continue
        extra = set(r) - {"version", "tag", "date", "notes", "assets"}
        if extra:
            errors.append(f"releases[{i}]: unknown keys: {', '.join(sorted(extra))}")
        v = _str(r, "version", errors, pattern=VERSION_RE, maxlen=41)
        if v in seen:
            errors.append(f"releases: version {v} is listed twice")
        seen.add(v)
        _str(r, "tag", errors, maxlen=100)
        if not isinstance(r.get("date"), _dt.date) or isinstance(r.get("date"), _dt.datetime):
            errors.append(f"releases[{i}].date must be a TOML date (YYYY-MM-DD)")
        _str(r, "notes", errors, required=False, maxlen=500)
        assets = r.get("assets")
        if not isinstance(assets, list) or not assets:
            errors.append(f"releases[{i}] needs at least one [[releases.assets]]")
            continue
        for j, a in enumerate(assets):
            if not isinstance(a, dict):
                errors.append(f"releases[{i}].assets[{j}] must be a table")
                continue
            extra = set(a) - {"name", "sha256", "macos"}
            if extra:
                errors.append(f"releases[{i}].assets[{j}]: unknown keys: {', '.join(sorted(extra))}")
            _str(a, "name", errors, maxlen=200)
            _str(a, "sha256", errors, pattern=SHA256_RE, maxlen=64)
            _str(a, "macos", errors, required=False, maxlen=20)
    return errors


REPORT_KEYS = {"kext", "version", "asset", "result", "date", "macos", "hardware", "features", "notes"}


def check_report(d, kext_entry):
    """Schema check of a report dict against its kext entry (a valid kext dict)."""
    errors = []
    unknown = set(d) - REPORT_KEYS
    if unknown:
        errors.append(f"unknown keys: {', '.join(sorted(unknown))}")
    k = _str(d, "kext", errors, maxlen=50)
    if k and kext_entry and k != kext_entry.get("id"):
        errors.append(f"`kext` ({k}) must be {kext_entry.get('id')}")
    v = _str(d, "version", errors, maxlen=41)
    releases = {r.get("version"): r for r in (kext_entry or {}).get("releases", []) if isinstance(r, dict)}
    if v and v not in releases:
        errors.append(f"`version` {v} is not a release listed in kext.toml")
    asset = _str(d, "asset", errors, required=False, maxlen=200)
    if asset and v in releases:
        names = {a.get("name") for a in releases[v].get("assets", []) if isinstance(a, dict)}
        if asset not in names:
            errors.append(f"`asset` {asset} is not an asset of release {v}")
    res = _str(d, "result", errors, maxlen=10)
    if res and res not in RESULTS:
        errors.append(f"`result` must be one of: {', '.join(sorted(RESULTS))}")
    date = d.get("date")
    if not isinstance(date, _dt.date) or isinstance(date, _dt.datetime):
        errors.append("`date` must be a TOML date (YYYY-MM-DD)")
    mac = d.get("macos")
    if not isinstance(mac, dict):
        errors.append("`[macos]` with `version` and `build` is required")
    else:
        _str(mac, "version", errors, pattern=MACOS_RE, maxlen=8)
        _str(mac, "build", errors, pattern=BUILD_RE, maxlen=8)
    hw = d.get("hardware")
    if not isinstance(hw, dict):
        errors.append("`[hardware]` is required")
    else:
        extra = set(hw) - {"cpu", "smbios", "bootloader", "device_ids", "board"}
        if extra:
            errors.append(f"hardware: unknown keys: {', '.join(sorted(extra))}")
        _str(hw, "cpu", errors, maxlen=80)
        _str(hw, "smbios", errors, maxlen=40)
        _str(hw, "bootloader", errors, required=False, maxlen=60)
        _str(hw, "board", errors, required=False, maxlen=80)
        _list_of_str(hw, "device_ids", errors, required=False, pattern=HW_ID_RE, maxitems=16)
    feats = d.get("features", {})
    if not isinstance(feats, dict):
        errors.append("`[features]` must be a table")
    else:
        if len(feats) > 30:
            errors.append("`[features]` has more than 30 entries")
        for name, state in feats.items():
            if not re.match(r"^[a-z0-9][a-z0-9-]{0,30}$", name):
                errors.append(f"feature name {name!r} must be lowercase letters, digits and dashes")
            if state not in FEATURE_STATES:
                errors.append(f"feature {name}: state must be one of {', '.join(sorted(FEATURE_STATES))}")
    _str(d, "notes", errors, required=False, maxlen=2000)
    return errors
