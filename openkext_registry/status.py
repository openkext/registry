# SPDX-License-Identifier: MIT
"""Status of a kext, computed from its reports. Nobody sets a status by hand.

For the newest release:
  community-verified  works/partial reports from at least COMMUNITY_MIN distinct accounts
                      that are not maintainers of the kext
  reported-broken     at least BROKEN_MIN distinct non-maintainer accounts report "broken",
                      and they outnumber the works/partial reports
  author-tested       a maintainer reports works/partial
  submitted           none of the above
One account counts once per release: its newest report wins.
"""
COMMUNITY_MIN = 3
BROKEN_MIN = 2


def latest_per_account(reports, version):
    """reports: [(login, dict)]. Newest report per login for `version`."""
    best = {}
    for login, r in reports:
        if r.get("version") != version:
            continue
        key = login.lower()
        if key not in best or r["date"] >= best[key][1]["date"]:
            best[key] = (login, r)
    return list(best.values())


def compute(entry, reports):
    # Newest by date; on the same date, the one listed last.
    rel = entry["releases"]
    latest = max(range(len(rel)), key=lambda i: (rel[i]["date"], i))
    latest = rel[latest]["version"]
    maint = {m.lower() for m in entry["maintainers"]}
    per = latest_per_account(reports, latest)
    ok_peer = sorted({l for l, r in per if l.lower() not in maint and r["result"] in ("works", "partial")})
    bad_peer = sorted({l for l, r in per if l.lower() not in maint and r["result"] == "broken"})
    ok_author = sorted({l for l, r in per if l.lower() in maint and r["result"] in ("works", "partial")})
    ok_all = len({l for l, r in per if r["result"] in ("works", "partial")})
    if len(bad_peer) >= BROKEN_MIN and len(bad_peer) > ok_all:
        status = "reported-broken"
    elif len(ok_peer) >= COMMUNITY_MIN:
        status = "community-verified"
    elif ok_author:
        status = "author-tested"
    else:
        status = "submitted"
    return {
        "status": status,
        "release": latest,
        "testers": ok_peer,
        "broken_reports": bad_peer,
        "author_tested": bool(ok_author),
        "reports_total": len(reports),
    }
