# Governance

The goal is a catalog that keeps working without anyone in charge of every decision. Fixed rules handle the common cases, other people's tests decide the status, and maintainers handle only what the rules can't.

## What the bot does

The bot runs on every pull request with the code from `main`. It never runs code from the pull request: it reads the changed files as data. It gives one of three answers:

- **approve**: every rule passed. The bot labels the pull request `bot:approved` and merges it once the checks are green.
- **fix**: a rule failed and the author can fix it (a wrong hash, a schema error, a report in the wrong folder). Label `bot:needs-fix`; the bot runs again on every push.
- **review**: the change is outside the rules. Label `needs-review`; a maintainer decides.

## Rules for a new project (approve)

1. The pull request only adds `kexts/<id>/kext.toml` and, optionally, the author's own reports for that project.
2. The file passes the schema in [docs/kext-format.md](docs/kext-format.md), and `id` matches the folder.
3. The author of the pull request is listed in `maintainers`.
4. The author's GitHub account is at least 30 days old.
5. `source` is a public GitHub repository.
6. The license is on the list below. Either GitHub detects that license for the repository, or `license_file` points at a file that contains that license's text at the release tag.
7. Every listed release exists as a published GitHub release, every listed asset exists, and its SHA-256 matches.

## Rules for an update (approve)

1. Only `kexts/<id>/kext.toml` of one project, sent by one of its current maintainers.
2. Only these fields change: `name`, `summary`, `categories`, `hardware`, `macos`, `homepage`, `based_on`, `ai_disclosure`, `license_file`, and new entries in `releases`.
3. Published releases are not edited or removed, and new releases pass rule 7 above.

## Rules for a test report (approve)

1. One new file in `kexts/<id>/reports/<login>/`, where `<login>` is the pull request author.
2. The report passes the schema in [docs/report-format.md](docs/report-format.md) and names a release that exists in `kext.toml`.
3. The author's account is at least 30 days old, and the date is not in the future.

## Always reviewed by a maintainer

- Anything outside `kexts/`: the rules, the bot, the workflows, the docs.
- Removing or renaming files, editing a published report, editing a published release.
- Changing a project's `id`, `source`, `license` or `maintainers`.
- Submitting a project you don't maintain (for example, an abandoned driver worth listing).
- Licenses not on the list, license files that don't match, archived repositories.
- Accounts younger than 30 days.
- Pull requests that touch more than one project.

`CODEOWNERS` enforces the first point: GitHub requires a maintainer's approval for any file outside `kexts/`.

## Licenses

Accepted automatically: GPL-2.0-only, GPL-2.0-or-later, GPL-3.0-only, GPL-3.0-or-later, LGPL-2.1-only, LGPL-2.1-or-later, MIT, BSD-2-Clause, BSD-3-Clause, ISC, Apache-2.0, MPL-2.0, APSL-2.0. Other OSI-approved licenses are fine after review. Projects that aren't open source aren't listed.

## What gets listed

Open-source kexts, patches, porting tools and documentation for running macOS on non-Apple hardware. The registry does not host binaries and doesn't link to anything that redistributes Apple software or helps get around activation or licensing.

## Abuse

Reports are public and tied to GitHub accounts. A maintainer can remove reports that are fake or part of a coordinated campaign, with a note in the pull request that removes them. Removals always go through review.

## Maintainers

Maintainers are listed in `CODEOWNERS`. New maintainers are added by pull request with the approval of an existing one. The aim is at least three, from different projects.

## Changing the rules

Rules change by pull request to `openkext_registry/rules.py` with tests and an update to this file, reviewed by a maintainer. Thresholds (30 days, 3 testers, 2 broken reports) are constants at the top of `rules.py` and `status.py`.
