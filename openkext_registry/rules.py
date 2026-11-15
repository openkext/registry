# SPDX-License-Identifier: MIT
"""The deterministic rules that decide what happens to a pull request.

Three outcomes:
  approve  every rule passed: the bot merges the pull request.
  fix      a rule failed in a way the contributor can fix: the bot comments and waits.
  review   the change is outside what the rules cover: a maintainer decides.

Input is data only: the list of changed files and a way to read file contents at the
base and head commits. Nothing from the pull request is executed.
"""
import datetime as _dt
import posixpath

from . import model

MIN_ACCOUNT_AGE_DAYS = 30
MAX_FILE_BYTES = 64 * 1024
# Fields a maintainer may change in an existing kext.toml without review.
FREE_EDIT_FIELDS = {"name", "summary", "categories", "hardware", "macos", "releases", "homepage",
                    "based_on", "ai_disclosure", "license_file"}


class Verdict:
    def __init__(self):
        self.kind = "unknown"
        self.fix = []
        self.review = []
        self.notes = []

    @property
    def decision(self):
        if self.fix:
            return "fix"
        if self.review:
            return "review"
        return "approve"

    def add_errors(self, prefix, errors):
        for e in errors:
            if e.startswith("REVIEW: "):
                self.review.append(f"{prefix}{e[8:]}")
            else:
                self.fix.append(f"{prefix}{e}")

    def to_dict(self):
        return {"decision": self.decision, "kind": self.kind, "fix": self.fix,
                "review": self.review, "notes": self.notes}


def _classify(path):
    """('kext', id) | ('report', id, login, name) | ('other',)."""
    parts = path.split("/")
    if path != posixpath.normpath(path) or parts[0] != "kexts":
        return ("other",)
    if len(parts) == 3 and parts[2] == "kext.toml":
        return ("kext", parts[1])
    if len(parts) == 5 and parts[2] == "reports":
        return ("report", parts[1], parts[3], parts[4])
    return ("other",)


def account_old_enough(gh, login, now, v):
    u = gh.user(login)
    if not u:
        v.fix.append(f"GitHub account {login} does not exist")
        return False
    created = _dt.datetime.fromisoformat(u["created_at"].replace("Z", "+00:00"))
    age = (now - created).days
    if age < MIN_ACCOUNT_AGE_DAYS:
        v.review.append(f"account {login} is {age} days old (the automatic limit is {MIN_ACCOUNT_AGE_DAYS})")
        return False
    return True


def check_source(gh, entry, v, releases=None):
    """Repository, license and release checks against GitHub. `releases` limits which are checked."""
    owner, name = model.GITHUB_REPO_RE.match(entry["source"]).groups()
    repo = gh.repo(owner, name)
    if not repo:
        v.fix.append(f"{entry['source']} does not exist or is not public")
        return
    if repo.get("private"):
        v.fix.append(f"{entry['source']} is private")
        return
    if repo.get("archived"):
        v.review.append(f"{entry['source']} is archived")
    to_check = [r for r in entry["releases"] if releases is None or r["version"] in releases]
    first_tag = to_check[0]["tag"] if to_check else repo.get("default_branch", "HEAD")
    spdx = entry["license"]
    detected = ((repo.get("license") or {}).get("spdx_id")) or "NOASSERTION"
    if entry.get("license_file"):
        text = gh.file_text(owner, name, entry["license_file"], first_tag)
        if text is None:
            v.fix.append(f"license_file {entry['license_file']} not found at {first_tag}")
        elif not model.license_text_matches(spdx, text):
            v.review.append(f"license_file {entry['license_file']} does not read like {spdx}")
    elif detected not in (spdx, spdx.removesuffix("-only"), spdx.removesuffix("-or-later")):
        # GitHub reports "GPL-2.0" for both -only and -or-later.
        v.review.append(f"GitHub detects the license as {detected}, the entry says {spdx}; "
                        "add `license_file` pointing at the license text, or a maintainer checks it")
    for r in to_check:
        rel = gh.release(owner, name, r["tag"])
        if not rel:
            v.fix.append(f"release {r['tag']} not found in {entry['source']}")
            continue
        if rel.get("draft"):
            v.fix.append(f"release {r['tag']} is a draft")
            continue
        by_name = {a["name"]: a for a in rel.get("assets", [])}
        for a in r["assets"]:
            ga = by_name.get(a["name"])
            if not ga:
                v.fix.append(f"release {r['tag']} has no asset named {a['name']}")
                continue
            try:
                digest = gh.asset_sha256(ga)
            except Exception as e:  # network and size errors
                v.review.append(f"could not hash {a['name']}: {e}")
                continue
            if digest != a["sha256"]:
                v.fix.append(f"{a['name']}: sha256 is {digest}, the entry says {a['sha256']}")


def _load(read, path, v, label):
    data = read(path)
    if data is None:
        return None
    if len(data) > MAX_FILE_BYTES:
        v.fix.append(f"{label}: file is larger than {MAX_FILE_BYTES} bytes")
        return None
    d, err = model.parse_toml(data)
    if err:
        v.fix.append(f"{label}: {err}")
    return d


def review(author, files, read_base, read_head, gh, now=None):
    """files: [{'filename', 'status'}] from the pulls API. read_*: path -> bytes or None."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    v = Verdict()
    if not files:
        v.review.append("the pull request changes no files")
        return v
    classes = []
    for f in files:
        c = _classify(f["filename"])
        if c[0] == "other":
            v.kind = "other"
            v.review.append(f"{f['filename']} is outside kexts/: maintainers review changes to the registry itself")
            return v
        if f["status"] not in ("added", "modified"):
            v.review.append(f"{f['filename']} is {f['status']}: removals and renames need review")
            return v
        classes.append((c, f))

    kext_ids = {c[1] for c, _ in classes}
    if len(kext_ids) != 1:
        v.review.append("the pull request touches more than one kext; send one pull request per kext")
        return v
    kid = kext_ids.pop()
    entry_path = f"kexts/{kid}/kext.toml"
    base_entry_raw = read_base(entry_path)
    kext_changes = [f for c, f in classes if c[0] == "kext"]
    reports = [(c, f) for c, f in classes if c[0] == "report"]

    if kext_changes:
        f = kext_changes[0]
        new = _load(read_head, entry_path, v, entry_path)
        if new is None:
            return v
        errs = model.check_kext(new, kid)
        v.add_errors(f"{entry_path}: ", errs)
        if [e for e in errs if not e.startswith("REVIEW: ")]:
            return v
        if base_entry_raw is None:
            v.kind = "new-kext"
            if author.lower() not in [m.lower() for m in new["maintainers"]]:
                v.review.append(f"{author} is not in `maintainers`: submitting someone else's project needs review")
            if not model.ID_RE.match(kid):
                v.fix.append(f"directory name {kid} is not a valid id")
            account_old_enough(gh, author, now, v)
            check_source(gh, new, v)
        else:
            v.kind = "kext-update"
            old, _ = model.parse_toml(base_entry_raw)
            old = old or {}
            if author.lower() not in [m.lower() for m in old.get("maintainers", [])]:
                v.review.append(f"{author} is not a maintainer of {kid}")
            changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
            locked = changed - FREE_EDIT_FIELDS
            if locked:
                v.review.append(f"changes to {', '.join(sorted(locked))} need review")
            old_rel = {r.get("version"): r for r in old.get("releases", []) if isinstance(r, dict)}
            for r in new["releases"]:
                if r["version"] in old_rel and old_rel[r["version"]] != r:
                    v.review.append(f"release {r['version']} was changed after publication")
            missing = set(old_rel) - {r["version"] for r in new["releases"]}
            if missing:
                v.review.append(f"releases removed: {', '.join(sorted(missing))}")
            new_versions = {r["version"] for r in new["releases"]} - set(old_rel)
            account_old_enough(gh, author, now, v)
            if new_versions:
                check_source(gh, new, v, releases=new_versions)
        entry = new
    else:
        if base_entry_raw is None:
            v.fix.append(f"{kid} is not in the registry")
            return v
        entry, _ = model.parse_toml(base_entry_raw)
        v.kind = "report"

    if reports:
        if v.kind == "report" and len(reports) > 1:
            v.review.append("send one report per pull request")
        for c, f in reports:
            _, _, login, fname = c
            label = f["filename"]
            if login.lower() != author.lower():
                v.fix.append(f"{label}: reports go in reports/{author}/ (your own GitHub login)")
                continue
            if not model.REPORT_NAME_RE.match(fname):
                v.fix.append(f"{label}: file name must be lowercase letters, digits, '.', '_' or '-', ending in .toml")
                continue
            if f["status"] != "added":
                v.review.append(f"{label}: editing a published report needs review; add a new one instead")
                continue
            d = _load(read_head, label, v, label)
            if d is None:
                continue
            v.add_errors(f"{label}: ", model.check_report(d, entry))
            if isinstance(d.get("date"), _dt.date) and d["date"] > now.date() + _dt.timedelta(days=1):
                v.fix.append(f"{label}: `date` is in the future")
        if v.kind == "report":
            account_old_enough(gh, author, now, v)
    return v
