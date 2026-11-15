# SPDX-License-Identifier: MIT
"""Read the whole registry from disk, check it, and build catalog.json for the site."""
import datetime as _dt
import json
import os

from . import model, status


def _jsonable(x):
    if isinstance(x, (_dt.date, _dt.datetime)):
        return x.isoformat()
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonable(v) for v in x]
    return x


def load(root):
    """Returns (kexts, errors). kexts: [{'entry', 'reports': [(login, dict, path)]}]."""
    kexts, errors = [], []
    base = os.path.join(root, "kexts")
    for kid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        d = os.path.join(base, kid)
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, "kext.toml")
        if not os.path.isfile(p):
            errors.append(f"kexts/{kid}: kext.toml missing")
            continue
        with open(p, "rb") as f:
            entry, err = model.parse_toml(f.read())
        if err:
            errors.append(f"kexts/{kid}/kext.toml: {err}")
            continue
        errs = [e.removeprefix("REVIEW: ") for e in model.check_kext(entry, kid)]
        errors += [f"kexts/{kid}/kext.toml: {e}" for e in errs]
        if errs:
            continue
        reports = []
        rdir = os.path.join(d, "reports")
        for login in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
            ldir = os.path.join(rdir, login)
            if not os.path.isdir(ldir) or not model.LOGIN_RE.match(login):
                errors.append(f"kexts/{kid}/reports/{login}: not a GitHub login directory")
                continue
            for name in sorted(os.listdir(ldir)):
                rp = f"kexts/{kid}/reports/{login}/{name}"
                if not model.REPORT_NAME_RE.match(name):
                    errors.append(f"{rp}: bad file name")
                    continue
                with open(os.path.join(ldir, name), "rb") as f:
                    r, err = model.parse_toml(f.read())
                if err:
                    errors.append(f"{rp}: {err}")
                    continue
                rerrs = model.check_report(r, entry)
                errors += [f"{rp}: {e}" for e in rerrs]
                if not rerrs:
                    reports.append((login, r, rp))
        kexts.append({"entry": entry, "reports": reports})
    return kexts, errors


def build(root):
    kexts, errors = load(root)
    out = []
    for k in kexts:
        e = k["entry"]
        st = status.compute(e, [(l, r) for l, r, _ in k["reports"]])
        out.append({
            **_jsonable(e),
            "status": st,
            "reports": [{"login": l, "path": p, **_jsonable(r)} for l, r, p in k["reports"]],
        })
    return {"schema": 1, "kexts": out}, errors


def write(root, path):
    cat, errors = build(root)
    with open(path, "w") as f:
        json.dump(cat, f, indent=2, sort_keys=True)
        f.write("\n")
    return errors
