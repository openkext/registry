# kext.toml

One file per project: `kexts/<id>/kext.toml`. TOML, UTF-8, under 64 KB.

```toml
id = "demo-wifi"                 # lowercase letters, digits and dashes; same as the folder
name = "Demo Wi-Fi"
summary = "One or two sentences, up to 280 characters."
kind = "kext"                    # kext | patch | tool | docs
categories = ["wifi"]            # wifi bluetooth audio graphics ethernet usb storage input power sensors cpu firmware other
source = "https://github.com/you/demo-wifi"
license = "GPL-2.0-only"         # SPDX id, see GOVERNANCE.md
license_file = "LICENSE"         # optional: path of the license text in the repository
maintainers = ["you"]            # GitHub logins
ai_disclosure = "none"           # or the AI tools and models used, e.g. "Claude Opus 5.5"
homepage = "https://..."         # optional
based_on = ["https://github.com/OpenIntelWireless/itlwm"]   # optional: upstream projects

[[hardware]]                     # optional, repeatable
vendor = "intel"
description = "Intel Wi-Fi 6E AX210"
pci_ids = ["8086:2725"]          # lowercase vvvv:dddd; usb_ids works the same way

[macos]                          # range you tested
min = "15.8"
max = "26.7"

[[releases]]                     # oldest first; repeat for each release
version = "1.0.0"
tag = "v1.0.0"                   # the GitHub release tag
date = 2026-11-15
notes = "Optional, up to 500 characters."

  [[releases.assets]]
  name = "DemoWiFi-1.0.0.zip"    # exact asset name in the GitHub release
  sha256 = "64 lowercase hex characters"
  macos = "26"                   # optional: which macOS this asset is for
```

Get the hash with `shasum -a 256 DemoWiFi-1.0.0.zip`.
