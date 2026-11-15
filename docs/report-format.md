# Test reports

One file per test: `kexts/<id>/reports/<your-github-login>/<name>.toml`. The name is up to you (lowercase letters, digits, `.`, `_`, `-`), for example `1.0.0-25g332.toml`.

```toml
kext = "demo-wifi"
version = "1.0.0"                # a release listed in kext.toml
asset = "DemoWiFi-1.0.0.zip"     # optional: which asset you installed
result = "works"                 # works | partial | broken
date = 2026-11-15
notes = "What you tested, what failed. Up to 2000 characters."

[macos]
version = "26.7.2"
build = "25G332"                 # sw_vers -buildVersion

[hardware]
cpu = "Intel Core i5-8500"
smbios = "iMac19,1"
bootloader = "OpenCore 1.0.8"    # optional
board = "Gigabyte B360M"         # optional
device_ids = ["8086:2725"]       # optional: the device the project drives

[features]                       # optional: name = works | partial | broken | untested
wifi = "works"
airdrop-send = "partial"
```

Don't include serial numbers, MAC addresses, network names or anything else personal. Reports are public.
