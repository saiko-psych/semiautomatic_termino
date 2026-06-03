# -*- coding: utf-8 -*-
"""
utils.unicloud
==============

Minimal WebDAV client for cloud.uni-graz.at (Nextcloud).

Operations: list, download, upload, upload_if_new, mkcol, delete, exists.

Authentication: HTTP Basic with the Nextcloud account name (NOT the email)
and an app password (cloud.uni-graz.at -> Settings -> Security ->
"Generate new app password"). The app password is fetched from the
keyring under "termino-uni / unicloud-app-pw".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
from urllib.parse import unquote

import requests

from utils.secrets import get_secret

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://cloud.uni-graz.at"
DAV_PREFIX = "/remote.php/dav/files"


class UniCloudError(RuntimeError):
    """Base class for uniCLOUD WebDAV errors."""


class UniCloudAuthError(UniCloudError):
    """401/403 from Nextcloud."""


class UniCloudNotFound(UniCloudError):
    """404 from Nextcloud."""


@dataclass
class WebDAVEntry:
    path: str
    is_dir: bool
    size: int
    etag: Optional[str]
    last_modified: Optional[str]


class UniCloudClient:
    """
    Tiny WebDAV client. Read the source - it does only what you see here.
    No hidden delete loops.
    """

    def __init__(
        self,
        username: str,
        app_password: Optional[str] = None,
        base_url: str = DEFAULT_BASE,
        timeout: float = 30.0,
    ):
        if not username:
            raise ValueError("Nextcloud username is required (not the email)")
        self.username = username
        self.base_url = base_url.rstrip("/")
        self.user_root = f"{self.base_url}{DAV_PREFIX}/{username}"
        self.timeout = timeout

        pw = app_password or get_secret("unicloud-app-pw")
        if not pw:
            raise UniCloudAuthError(
                "No uniCLOUD app password in keyring. Run: "
                "python -m utils.secrets set --termino  "
                "and store one under 'unicloud-app-pw'."
            )
        self._auth = (username, pw)

    def _url(self, remote_path: str) -> str:
        if not remote_path.startswith("/"):
            remote_path = "/" + remote_path
        return self.user_root + remote_path

    def _check(self, resp: requests.Response, ctx: str) -> None:
        if resp.status_code in (401, 403):
            raise UniCloudAuthError(
                f"{ctx}: HTTP {resp.status_code} - check Nextcloud username "
                f"and app password. URL: {resp.request.url}"
            )
        if resp.status_code == 404:
            raise UniCloudNotFound(f"{ctx}: not found ({resp.request.url})")
        if resp.status_code >= 400:
            raise UniCloudError(
                f"{ctx}: HTTP {resp.status_code} "
                f"({resp.text[:200] if resp.text else 'no body'})"
            )

    # ----- read operations ----------------------------------------------

    def list(self, remote_path: str = "/") -> list:
        url = self._url(remote_path)
        body = (
            '<?xml version="1.0"?>'
            '<d:propfind xmlns:d="DAV:">'
            '<d:prop>'
            '<d:resourcetype/>'
            '<d:getcontentlength/>'
            '<d:getetag/>'
            '<d:getlastmodified/>'
            '</d:prop>'
            '</d:propfind>'
        )
        resp = requests.request(
            "PROPFIND", url,
            auth=self._auth,
            headers={"Depth": "1", "Content-Type": "application/xml"},
            data=body, timeout=self.timeout,
        )
        self._check(resp, f"PROPFIND {remote_path}")
        return self._parse_propfind(resp.text)

    def download(self, remote_path: str, local_path: Path) -> str:
        url = self._url(remote_path)
        resp = requests.get(url, auth=self._auth, timeout=self.timeout, stream=True)
        self._check(resp, f"GET {remote_path}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
        etag = resp.headers.get("ETag", "").strip('"')
        log.info("downloaded %s -> %s (%d bytes, etag=%s)",
                 remote_path, local_path, local_path.stat().st_size, etag)
        return etag

    def exists(self, remote_path: str) -> bool:
        url = self._url(remote_path)
        resp = requests.head(url, auth=self._auth, timeout=self.timeout)
        if resp.status_code == 404:
            return False
        if resp.status_code in (200, 207):
            return True
        self._check(resp, f"HEAD {remote_path}")
        return False

    # ----- write operations ---------------------------------------------

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        if_match: Optional[str] = None,
    ) -> str:
        """Overwrite-allowed upload. Pass if_match=<etag> for safe overwrite."""
        url = self._url(remote_path)
        headers = {}
        if if_match:
            headers["If-Match"] = f'"{if_match}"'
        with open(local_path, "rb") as f:
            resp = requests.put(url, data=f, auth=self._auth,
                                headers=headers, timeout=self.timeout)
        if resp.status_code == 412:
            raise UniCloudError(
                f"PUT {remote_path}: 412 Precondition Failed - file was "
                f"modified since last download. Re-download and retry."
            )
        self._check(resp, f"PUT {remote_path}")
        new_etag = resp.headers.get("ETag", "").strip('"')
        log.info("uploaded %s -> %s (etag=%s)", local_path, remote_path, new_etag)
        return new_etag

    def upload_if_new(self, local_path: Path, remote_path: str) -> str:
        """
        Upload ONLY if the remote file does not exist. Uses ``If-None-Match: *``
        so the server enforces the precondition - no race condition.
        Raises UniCloudError if the file is already there.
        """
        url = self._url(remote_path)
        with open(local_path, "rb") as f:
            resp = requests.put(
                url, data=f, auth=self._auth,
                headers={"If-None-Match": "*"},
                timeout=self.timeout,
            )
        if resp.status_code == 412:
            raise UniCloudError(
                f"PUT {remote_path}: 412 Precondition Failed - the file "
                f"already exists on uniCLOUD. Not overwriting."
            )
        self._check(resp, f"PUT {remote_path} (if-new)")
        etag = resp.headers.get("ETag", "").strip('"')
        log.info("uploaded NEW %s -> %s (etag=%s)",
                 local_path, remote_path, etag)
        return etag

    def mkcol(self, remote_path: str) -> None:
        """Create one directory. 405 (already exists) is silently ok."""
        url = self._url(remote_path)
        resp = requests.request("MKCOL", url, auth=self._auth,
                                timeout=self.timeout)
        if resp.status_code == 405:
            return
        self._check(resp, f"MKCOL {remote_path}")
        log.info("created directory %s", remote_path)

    def delete(self, remote_path: str) -> None:
        url = self._url(remote_path)
        resp = requests.delete(url, auth=self._auth, timeout=self.timeout)
        self._check(resp, f"DELETE {remote_path}")

    # ----- helpers ------------------------------------------------------

    def _parse_propfind(self, xml_text: str) -> list:
        ns = {"d": "DAV:"}
        root = ET.fromstring(xml_text)
        entries = []
        href_prefix = f"{DAV_PREFIX}/{self.username}"
        for resp in root.findall("d:response", ns):
            href_el = resp.find("d:href", ns)
            if href_el is None or not href_el.text:
                continue
            href = href_el.text
            if href.startswith(href_prefix):
                rel = href[len(href_prefix):] or "/"
            else:
                rel = href
            rel = unquote(rel)
            is_dir = (
                resp.find(".//d:resourcetype/d:collection", ns) is not None
            )
            size_el = resp.find(".//d:getcontentlength", ns)
            size = int(size_el.text) if size_el is not None and size_el.text else 0
            etag_el = resp.find(".//d:getetag", ns)
            etag = etag_el.text.strip('"') if etag_el is not None and etag_el.text else None
            lm_el = resp.find(".//d:getlastmodified", ns)
            last_modified = lm_el.text if lm_el is not None else None
            entries.append(WebDAVEntry(
                path=rel,
                is_dir=is_dir,
                size=size,
                etag=etag,
                last_modified=last_modified,
            ))
        return entries
