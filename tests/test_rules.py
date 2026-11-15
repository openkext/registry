# SPDX-License-Identifier: MIT
import datetime as dt
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from openkext_registry import catalog, model, rules, status  # noqa: E402

NOW = dt.datetime(2026, 11, 15, 12, tzinfo=dt.timezone.utc)
GPL2 = "GNU GENERAL PUBLIC LICENSE\n   Version 2, June 1991\n..."
SHA = "a" * 64

ENTRY = """id = "demo-wifi"
name = "Demo"
summary = "A demo driver."
kind = "kext"
categories = ["wifi"]
source = "https://github.com/alice/demo"
license = "GPL-2.0-only"
license_file = "LICENSE"
maintainers = ["alice"]
ai_disclosure = "none"

[macos]
min = "15.0"
max = "26.7"

[[releases]]
version = "1.0.0"
tag = "v1.0.0"
date = 2026-11-01
  [[releases.assets]]
  name = "Demo.zip"
  sha256 = "%s"
""" % SHA

RELEASE2 = """
[[releases]]
version = "1.1.0"
tag = "v1.1.0"
date = 2026-11-10
  [[releases.assets]]
  name = "Demo.zip"
  sha256 = "%s"
""" % SHA

REPORT = """kext = "demo-wifi"
version = "1.0.0"
result = "works"
date = 2026-11-14
[macos]
version = "26.7.2"
build = "25G332"
[hardware]
cpu = "Intel i5-8500"
smbios = "iMac19,1"
[features]
wifi = "works"
"""


class FakeGH:
    def __init__(self):
        self.users = {"alice": "2020-01-01T00:00:00Z", "bob": "2021-01-01T00:00:00Z",
                      "newbie": "2026-11-10T00:00:00Z"}
        self.repos = {("alice", "demo"): {"private": False, "archived": False, "license": {"spdx_id": "NOASSERTION"}}}
        self.files = {("alice", "demo", "LICENSE"): GPL2}
        self.releases = {"v1.0.0": [{"name": "Demo.zip", "size": 10, "sha": SHA}],
                         "v1.1.0": [{"name": "Demo.zip", "size": 10, "sha": SHA}]}

    def user(self, login):
        c = self.users.get(login.lower())
        return {"login": login, "created_at": c} if c else None

    def repo(self, o, n):
        return self.repos.get((o, n))

    def file_text(self, o, n, path, ref):
        return self.files.get((o, n, path))

    def release(self, o, n, tag):
        a = self.releases.get(tag)
        return None if a is None else {"draft": False, "assets": a}

    def asset_sha256(self, asset):
        return asset["sha"]


def reader(files):
    return lambda p: files[p].encode() if p in files else None


def run(author, changes, base, head, gh=None):
    files = [{"filename": p, "status": s} for p, s in changes]
    return rules.review(author, files, reader(base), reader(head), gh or FakeGH(), now=NOW)


E = "kexts/demo-wifi/kext.toml"
R = "kexts/demo-wifi/reports/{}/r1.toml"


class NewKext(unittest.TestCase):
    def test_valid_submission_is_approved(self):
        v = run("alice", [(E, "added")], {}, {E: ENTRY})
        self.assertEqual(v.decision, "approve", v.to_dict())
        self.assertEqual(v.kind, "new-kext")

    def test_with_own_report(self):
        v = run("alice", [(E, "added"), (R.format("alice"), "added")], {}, {E: ENTRY, R.format("alice"): REPORT})
        self.assertEqual(v.decision, "approve", v.to_dict())

    def test_submitter_not_maintainer_needs_review(self):
        self.assertEqual(run("bob", [(E, "added")], {}, {E: ENTRY}).decision, "review")

    def test_young_account_needs_review(self):
        e = ENTRY.replace('["alice"]', '["newbie"]')
        self.assertEqual(run("newbie", [(E, "added")], {}, {E: e}).decision, "review")

    def test_bad_hash_must_be_fixed(self):
        gh = FakeGH()
        gh.releases["v1.0.0"][0]["sha"] = "b" * 64
        self.assertEqual(run("alice", [(E, "added")], {}, {E: ENTRY}, gh).decision, "fix")

    def test_missing_release_must_be_fixed(self):
        gh = FakeGH()
        del gh.releases["v1.0.0"]
        self.assertEqual(run("alice", [(E, "added")], {}, {E: ENTRY}, gh).decision, "fix")

    def test_private_or_missing_repo(self):
        gh = FakeGH()
        gh.repos.clear()
        self.assertEqual(run("alice", [(E, "added")], {}, {E: ENTRY}, gh).decision, "fix")

    def test_license_not_on_list_needs_review(self):
        e = ENTRY.replace("GPL-2.0-only", "LicenseRef-custom")
        self.assertEqual(run("alice", [(E, "added")], {}, {E: e}).decision, "review")

    def test_license_file_text_mismatch_needs_review(self):
        gh = FakeGH()
        gh.files[("alice", "demo", "LICENSE")] = "All rights reserved."
        self.assertEqual(run("alice", [(E, "added")], {}, {E: ENTRY}, gh).decision, "review")

    def test_detected_license_without_license_file(self):
        e = ENTRY.replace('license_file = "LICENSE"\n', "")
        gh = FakeGH()
        gh.repos[("alice", "demo")]["license"] = {"spdx_id": "GPL-2.0"}
        self.assertEqual(run("alice", [(E, "added")], {}, {E: e}, gh).decision, "approve")
        gh.repos[("alice", "demo")]["license"] = {"spdx_id": "MIT"}
        self.assertEqual(run("alice", [(E, "added")], {}, {E: e}, gh).decision, "review")

    def test_schema_error_must_be_fixed(self):
        e = ENTRY.replace('kind = "kext"', 'kind = "virus"')
        self.assertEqual(run("alice", [(E, "added")], {}, {E: e}).decision, "fix")

    def test_unknown_key(self):
        self.assertEqual(run("alice", [(E, "added")], {}, {E: ENTRY + 'extra = 1\n'}).decision, "fix")

    def test_id_must_match_dir(self):
        e = ENTRY.replace('id = "demo-wifi"', 'id = "other"')
        self.assertEqual(run("alice", [(E, "added")], {}, {E: e}).decision, "fix")

    def test_invalid_toml(self):
        self.assertEqual(run("alice", [(E, "added")], {}, {E: "id = "}).decision, "fix")


class Scope(unittest.TestCase):
    def test_outside_kexts_needs_review(self):
        v = run("alice", [("openkext_registry/rules.py", "modified")], {}, {})
        self.assertEqual(v.decision, "review")

    def test_workflow_change_needs_review(self):
        v = run("alice", [(E, "added"), (".github/workflows/bot.yml", "modified")], {}, {E: ENTRY})
        self.assertEqual(v.decision, "review")

    def test_two_kexts_need_review(self):
        e2 = "kexts/other/kext.toml"
        self.assertEqual(run("alice", [(E, "added"), (e2, "added")], {}, {E: ENTRY, e2: ENTRY}).decision, "review")

    def test_removal_needs_review(self):
        self.assertEqual(run("alice", [(E, "removed")], {E: ENTRY}, {}).decision, "review")

    def test_path_tricks(self):
        for p in ["kexts/../x/kext.toml", "kexts/demo-wifi/./kext.toml", "kexts/demo-wifi/extra/kext.toml"]:
            self.assertEqual(run("alice", [(p, "added")], {}, {p: ENTRY}).decision, "review", p)

    def test_empty(self):
        self.assertEqual(run("alice", [], {}, {}).decision, "review")


class Update(unittest.TestCase):
    def test_maintainer_adds_release(self):
        v = run("alice", [(E, "modified")], {E: ENTRY}, {E: ENTRY + RELEASE2})
        self.assertEqual(v.decision, "approve", v.to_dict())
        self.assertEqual(v.kind, "kext-update")

    def test_non_maintainer_update_needs_review(self):
        self.assertEqual(run("bob", [(E, "modified")], {E: ENTRY}, {E: ENTRY + RELEASE2}).decision, "review")

    def test_changing_maintainers_needs_review(self):
        new = ENTRY.replace('["alice"]', '["alice", "bob"]')
        self.assertEqual(run("alice", [(E, "modified")], {E: ENTRY}, {E: new}).decision, "review")

    def test_changing_source_needs_review(self):
        new = ENTRY.replace("alice/demo", "alice/demo2")
        self.assertEqual(run("alice", [(E, "modified")], {E: ENTRY}, {E: new}).decision, "review")

    def test_rewriting_published_release_needs_review(self):
        new = ENTRY.replace(SHA, "c" * 64)
        self.assertEqual(run("alice", [(E, "modified")], {E: ENTRY}, {E: new}).decision, "review")

    def test_summary_edit(self):
        new = ENTRY.replace("A demo driver.", "A better demo driver.")
        self.assertEqual(run("alice", [(E, "modified")], {E: ENTRY}, {E: new}).decision, "approve")


class Reports(unittest.TestCase):
    def test_peer_report_approved(self):
        v = run("bob", [(R.format("bob"), "added")], {E: ENTRY}, {E: ENTRY, R.format("bob"): REPORT})
        self.assertEqual(v.decision, "approve", v.to_dict())
        self.assertEqual(v.kind, "report")

    def test_report_in_someone_elses_folder(self):
        v = run("bob", [(R.format("carol"), "added")], {E: ENTRY}, {E: ENTRY, R.format("carol"): REPORT})
        self.assertEqual(v.decision, "fix")

    def test_login_case_insensitive(self):
        v = run("Bob", [(R.format("bob"), "added")], {E: ENTRY}, {E: ENTRY, R.format("bob"): REPORT})
        self.assertEqual(v.decision, "approve")

    def test_report_for_unknown_version(self):
        rep = REPORT.replace('version = "1.0.0"', 'version = "9.9"')
        v = run("bob", [(R.format("bob"), "added")], {E: ENTRY}, {E: ENTRY, R.format("bob"): rep})
        self.assertEqual(v.decision, "fix")

    def test_report_for_unknown_kext(self):
        v = run("bob", [(R.format("bob"), "added")], {}, {R.format("bob"): REPORT})
        self.assertEqual(v.decision, "fix")

    def test_editing_report_needs_review(self):
        v = run("bob", [(R.format("bob"), "modified")], {E: ENTRY, R.format("bob"): REPORT},
                {E: ENTRY, R.format("bob"): REPORT.replace("works", "broken", 1)})
        self.assertEqual(v.decision, "review")

    def test_young_account_report_needs_review(self):
        v = run("newbie", [(R.format("newbie"), "added")], {E: ENTRY}, {E: ENTRY, R.format("newbie"): REPORT})
        self.assertEqual(v.decision, "review")

    def test_future_date(self):
        rep = REPORT.replace("2026-11-14", "2027-01-01")
        v = run("bob", [(R.format("bob"), "added")], {E: ENTRY}, {E: ENTRY, R.format("bob"): rep})
        self.assertEqual(v.decision, "fix")

    def test_bad_feature_state(self):
        rep = REPORT.replace('wifi = "works"', 'wifi = "great"')
        v = run("bob", [(R.format("bob"), "added")], {E: ENTRY}, {E: ENTRY, R.format("bob"): rep})
        self.assertEqual(v.decision, "fix")

    def test_bad_file_name(self):
        p = "kexts/demo-wifi/reports/bob/My Report.toml"
        v = run("bob", [(p, "added")], {E: ENTRY}, {E: ENTRY, p: REPORT})
        self.assertEqual(v.decision, "fix")


def rep(result, version="1.0.0", date=dt.date(2026, 11, 14)):
    return {"version": version, "result": result, "date": date}


class Status(unittest.TestCase):
    entry = model.parse_toml(ENTRY.encode())[0]

    def test_submitted(self):
        self.assertEqual(status.compute(self.entry, [])["status"], "submitted")

    def test_author_tested(self):
        self.assertEqual(status.compute(self.entry, [("alice", rep("works"))])["status"], "author-tested")

    def test_community_needs_three_distinct_non_maintainers(self):
        r = [("alice", rep("works")), ("bob", rep("works")), ("BOB", rep("works")), ("carol", rep("partial"))]
        self.assertEqual(status.compute(self.entry, r)["status"], "author-tested")
        r.append(("dave", rep("works")))
        self.assertEqual(status.compute(self.entry, r)["status"], "community-verified")

    def test_newest_report_per_account_wins(self):
        r = [("bob", rep("works")), ("bob", rep("broken", date=dt.date(2026, 11, 15))),
             ("carol", rep("broken")), ("dave", rep("works"))]
        st = status.compute(self.entry, r)
        self.assertEqual(st["broken_reports"], ["bob", "carol"])
        self.assertEqual(st["status"], "reported-broken")

    def test_only_latest_release_counts(self):
        e = model.parse_toml((ENTRY + RELEASE2).encode())[0]
        r = [("bob", rep("works")), ("carol", rep("works")), ("dave", rep("works"))]
        self.assertEqual(status.compute(e, r)["status"], "submitted")


class Registry(unittest.TestCase):
    def test_repository_data_is_valid(self):
        _, errors = catalog.build(ROOT)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
