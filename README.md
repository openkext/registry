# OpenKext registry

The catalog of open-source macOS drivers (kexts), patches and porting tools for hackintosh hardware. Each entry points to the project's own repository and releases; nothing is hosted here except metadata and test reports.

The site at [openkext.org](https://openkext.org) is built from this repository.

## How it works

- **Anyone can submit a project** with a pull request that adds `kexts/<id>/kext.toml`.
- **Anyone can report a test** with a pull request that adds a file under `kexts/<id>/reports/<your-github-login>/`.
- **A bot applies fixed rules** to every pull request. If they all pass, it merges. If a rule fails, it says which one. If the change is outside what the rules cover, a maintainer reviews it. The rules are in [GOVERNANCE.md](GOVERNANCE.md) and in `openkext_registry/rules.py`, with tests.
- **Status comes from reports, not from maintainers.** A project becomes `community-verified` when three different people (not its maintainers) report it working on its newest release.

| Status | Meaning |
|---|---|
| `submitted` | Listed; the rules checked the source, license and release hashes, but nobody has reported a test yet |
| `author-tested` | A maintainer of the project reports it working |
| `community-verified` | At least 3 accounts that don't maintain it report it working or partly working on the newest release |
| `reported-broken` | At least 2 such accounts report it broken, and they outnumber the working reports |

## Submit a project

1. Your project must be open source under a license on the [automatic list](GOVERNANCE.md#licenses), hosted on GitHub, with a GitHub release whose assets you list with their SHA-256.
2. Copy [docs/kext-format.md](docs/kext-format.md)'s example into `kexts/<id>/kext.toml`. Put yourself in `maintainers`.
3. Optional: add your own test report in the same pull request.
4. Open the pull request. The bot answers in a minute or two.

Run the checks locally with `python3 tools/check_registry.py` (Python 3.11+, no dependencies).

## Report a test

Run `python3 tools/make_report.py <id> <version> works|partial|broken --login <you> --write` on the tested Mac, or write `kexts/<id>/reports/<your-login>/<anything>.toml` by hand following [docs/report-format.md](docs/report-format.md) and open a pull request. One report per pull request. Your newest report for a release is the one that counts; to change your result, add a new file instead of editing the old one.

## For tools and AI agents

JSON Schemas for both file formats are in [`schema/`](schema/), `tools/make_report.py` writes a report from the Mac it runs on, and [AGENTS.md](AGENTS.md) explains how an AI agent should work with this repository. The site publishes the catalog as JSON (`catalog.json`, `api/`) and an index for LLMs (`llms.txt`).

## License

Code (`openkext_registry/`, `tools/`, `tests/`, workflows): MIT. The data in `kexts/` is CC0-1.0, so anyone can reuse the catalog. Each listed project keeps its own license.
