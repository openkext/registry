# SPDX-License-Identifier: MIT
"""Minimal read-only GitHub REST client (standard library only)."""
import hashlib
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"
MAX_ASSET_BYTES = 100 * 1024 * 1024


class GitHubError(Exception):
    pass


class GitHub:
    def __init__(self, token=None):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")

    def _request(self, url, accept="application/vnd.github+json"):
        req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "openkext-registry-bot",
                                                   "X-GitHub-Api-Version": "2022-11-28"})
        if self.token and url.startswith(API):
            req.add_header("Authorization", f"Bearer {self.token}")
        return urllib.request.urlopen(req, timeout=60)

    def _json(self, path):
        try:
            with self._request(API + path) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise GitHubError(f"GET {path}: HTTP {e.code}") from e

    def user(self, login):
        """{'login', 'created_at', 'type'} or None."""
        return self._json(f"/users/{login}")

    def repo(self, owner, name):
        return self._json(f"/repos/{owner}/{name}")

    def release(self, owner, name, tag):
        return self._json(f"/repos/{owner}/{name}/releases/tags/{urllib.request.quote(tag, safe='')}")

    def file_text(self, owner, name, path, ref):
        """Raw text of a file at a ref, or None."""
        url = f"{API}/repos/{owner}/{name}/contents/{urllib.request.quote(path)}?ref={urllib.request.quote(ref, safe='')}"
        try:
            with self._request(url, accept="application/vnd.github.raw") as r:
                return r.read(2 * 1024 * 1024).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise GitHubError(f"GET {path}@{ref}: HTTP {e.code}") from e

    def asset_sha256(self, asset):
        """SHA-256 of a release asset (dict from the releases API), streamed, size-capped."""
        if asset.get("size", 0) > MAX_ASSET_BYTES:
            raise GitHubError(f"{asset.get('name')} is larger than {MAX_ASSET_BYTES // (1024 * 1024)} MB")
        h = hashlib.sha256()
        total = 0
        with self._request(asset["browser_download_url"], accept="application/octet-stream") as r:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ASSET_BYTES:
                    raise GitHubError(f"{asset.get('name')} is larger than the limit")
                h.update(chunk)
        return h.hexdigest()
