#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_REPO = "derek-betz/BidTabsData"
DEFAULT_OUT_DIR = "data-sample/BidTabsData"
API_ACCEPT = "application/vnd.github+json"
FILE_TYPE_MASK = 0o170000  # matches stat.S_IFMT
SYMLINK_MODE = 0o120000    # matches stat.S_IFLNK


def build_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {"Accept": API_ACCEPT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def require_version() -> str:
    version = os.environ.get("BIDTABSDATA_VERSION")
    if not version:
        raise SystemExit("BIDTABSDATA_VERSION is required")
    return version


def resolve_repo() -> str:
    return os.environ.get("BIDTABSDATA_REPO", DEFAULT_REPO)


def resolve_out_dir() -> Path:
    return Path(os.environ.get("BIDTABSDATA_OUT_DIR", DEFAULT_OUT_DIR))


def fetch_release(repo: str, version: str, headers: Dict[str, str]) -> Dict:
    url = f"https://api.github.com/repos/{repo}/releases/tags/{version}"
    try:
        with urlopen(Request(url, headers=headers)) as response:
            return json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"Failed to load release {repo}@{version}: {exc}") from exc
    except URLError as exc:
        raise SystemExit(f"Failed to reach GitHub: {exc}") from exc


def pick_asset(assets: Iterable[Dict]) -> Dict:
    chosen: List[Dict] = [a for a in assets if a.get("name", "").lower().endswith(".zip")]
    if not chosen:
        raise SystemExit("No zip release assets found to download")
    return chosen[0]


def download_asset(url: str, dest: Path, headers: Dict[str, str]) -> None:
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as response, open(dest, "wb") as f:
            shutil.copyfileobj(response, f)
    except HTTPError as exc:
        raise SystemExit(f"Failed to download asset: {exc}") from exc
    except URLError as exc:
        raise SystemExit(f"Failed to reach GitHub while downloading asset: {exc}") from exc


def extract_zip(zip_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            dest_root = destination.resolve()
            for member in zip_file.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise SystemExit(f"Unsafe path in archive: {member.filename}")
                target_path = (dest_root / member_path).resolve()
                if not str(target_path).startswith(str(dest_root)):
                    raise SystemExit(f"Unsafe path in archive: {member.filename}")
                mode = (member.external_attr >> 16) & FILE_TYPE_MASK
                if mode == SYMLINK_MODE:
                    raise SystemExit(f"Symlinks are not allowed in archive: {member.filename}")
                zip_file.extract(member, destination)
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Asset is not a valid zip archive: {exc}") from exc


def locate_payload(extracted_root: Path) -> Path:
    entries = [p for p in extracted_root.iterdir() if p.name != "__MACOSX" and not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted_root


def write_version_marker(target_dir: Path, version: str) -> None:
    marker = target_dir / ".bidtabsdata_version"
    marker.write_text(f"{version}\n")


def main() -> None:
    version = require_version()
    repo = resolve_repo()
    out_dir = resolve_out_dir()
    out_dir_parent = out_dir.resolve().parent
    headers = build_headers()

    release = fetch_release(repo, version, headers)
    asset = pick_asset(release.get("assets", []))

    print(f"Fetching BidTabsData {version} from {repo}")
    print(f"Selected asset: {asset.get('name')}")

    out_dir_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bidtabsdata_", dir=out_dir_parent) as tmpdir:
        download_url = asset.get("browser_download_url")
        if not download_url:
            raise SystemExit("Selected asset is missing a browser_download_url")

        asset_name = asset.get("name") or "BidTabsData.zip"
        if "/" in asset_name or "\\" in asset_name:
            raise SystemExit("Selected asset name contains path separators")
        download_path = Path(tmpdir) / asset_name
        extract_root = Path(tmpdir) / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)

        download_asset(download_url, download_path, headers)
        extract_zip(download_path, extract_root)

        payload_root = locate_payload(extract_root)
        write_version_marker(payload_root, version)

        staging_dir = out_dir_parent / f".{out_dir.name}.staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        payload_root.rename(staging_dir)

        backup_dir = out_dir_parent / f".{out_dir.name}.old"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        try:
            if out_dir.exists():
                out_dir.rename(backup_dir)
            staging_dir.rename(out_dir)
        except (FileExistsError, PermissionError):
            if backup_dir.exists() and not out_dir.exists():
                try:
                    backup_dir.rename(out_dir)
                except Exception:
                    pass
            raise
        else:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    print(f"Wrote BidTabsData to {out_dir}")


if __name__ == "__main__":
    main()
