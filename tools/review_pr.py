#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Review one pull request with the registry rules. Used by the bot workflow.

    review_pr.py PR_NUMBER BASE_SHA HEAD_SHA OUT_JSON

Reads changed files through the GitHub API and file contents with `git show`, so the
pull request's own code is never run. Writes the verdict as JSON and prints a Markdown
comment on stdout.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from openkext_registry import github, rules  # noqa: E402


def git_reader(sha):
    def read(path):
        r = subprocess.run(["git", "show", f"{sha}:{path}"], capture_output=True)
        return r.stdout if r.returncode == 0 else None
    return read


def main():
    number, base, head, out = sys.argv[1:5]
    repo = os.environ["GITHUB_REPOSITORY"]
    gh = github.GitHub()
    pr = gh._json(f"/repos/{repo}/pulls/{number}")
    files = []
    for page in range(1, 4):
        batch = gh._json(f"/repos/{repo}/pulls/{number}/files?per_page=100&page={page}") or []
        files += [{"filename": f["filename"], "status": f["status"]} for f in batch]
        if len(batch) < 100:
            break
    v = rules.review(pr["user"]["login"], files, git_reader(base), git_reader(head), gh)
    if pr["head"]["sha"] != head:
        v.review.append("the pull request changed while it was being checked; run again")
    d = v.to_dict()
    with open(out, "w") as f:
        json.dump(d, f, indent=2)
    title = {"approve": "All rules passed. Merging.",
             "fix": "Some rules failed. Push a fix and the check runs again.",
             "review": "This needs a maintainer: it is outside what the automatic rules cover."}[d["decision"]]
    lines = [f"**OpenKext bot** ({d['kind']}): {title}", ""]
    for e in d["fix"]:
        lines.append(f"- [ ] {e}")
    for e in d["review"]:
        lines.append(f"- review: {e}")
    lines += ["", f"Rules: [GOVERNANCE.md](https://github.com/{repo}/blob/main/GOVERNANCE.md)"]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
