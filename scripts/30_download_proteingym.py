#!/usr/bin/env python
"""30_download_proteingym.py — fetch the ProteinGym substitutions benchmark.

v1.3, 217 DMS assays, ~2.7M missense variants, ~1 GB unzipped. We only need
the substitutions zip (43 MB compressed) — not the 1.7 GB baseline-scores
archive (published zero-shot scores stay a phase-2 addition).

Two mirrors, resume-support for flaky Wi-Fi:
  1. marks.hms.harvard.edu (Harvard mirror, canonical per ProteinGym README)
  2. zenodo.org/records/15293562 (archival, v1.3)

Writes data/proteingym/substitutions/*.csv (flattened) and a small manifest
into data/report/proteingym_download.json.

Usage:
    python scripts/30_download_proteingym.py            # download + unzip
    python scripts/30_download_proteingym.py --list-only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PG_DIR = REPO / "data" / "proteingym"
REPORT = REPO / "data" / "report"

MIRRORS = [
    "https://marks.hms.harvard.edu/proteingym/ProteinGym_v1.3/"
    "DMS_ProteinGym_substitutions.zip",
    "https://zenodo.org/records/15293562/files/"
    "DMS_ProteinGym_substitutions.zip?download=1",
]


def head_size(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        n = r.headers.get("Content-Length")
        return int(n) if n else None


def download(url: str, dest: Path, retries: int = 4) -> Path:
    """Streaming download with Range-resume; falls back on non-206 servers."""
    for attempt in range(retries):
        have = dest.stat().st_size if dest.exists() else 0
        req = urllib.request.Request(url)
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=60) as r, \
                 dest.open("ab" if have and r.status == 206 else "wb") as f:
                total = have + int(r.headers.get("Content-Length", 0) or 0)
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done = dest.stat().st_size
                    if total:
                        print(f"\r  {done / 1e6:7.1f} / {total / 1e6:7.1f} MB",
                              end="", flush=True)
            print()
            if not total or dest.stat().st_size == total:
                return dest
            print(f"  incomplete ({dest.stat().st_size} != {total}), retrying")
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"download failed after {retries} attempts: {url}")


def extract(zip_path: Path, dest: Path) -> tuple[list[str], int]:
    """Flatten archive members (they sit under a top-level folder) into dest."""
    dest.mkdir(parents=True, exist_ok=True)
    files, rows = [], 0
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            if not m.filename.lower().endswith(".csv") or m.is_dir():
                continue
            name = m.filename.rsplit("/", 1)[-1]
            src = dest / m.filename
            if not src.exists():
                z.extract(m, dest)
            if src != dest / name:
                src.rename(dest / name)
            files.append(name)
            rows += sum(1 for _ in (dest / name).open("rb"))
    return files, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list-only", action="store_true",
                    help="HEAD each mirror and exit")
    ap.add_argument("--url", default=None, help="override download URL")
    args = ap.parse_args()

    urls = [args.url] if args.url else MIRRORS
    sizes = {}
    for u in urls:
        try:
            sizes[u] = head_size(u)
            print(f"mirror ok: {u}  ({(sizes[u] or 0) / 1e6:.0f} MB)")
        except Exception as e:  # noqa: BLE001
            print(f"mirror unreachable: {u}  ({e})")
    if args.list_only or not sizes:
        return

    PG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    zip_path = PG_DIR / "DMS_ProteinGym_substitutions.zip"
    url = next(iter(sizes))
    want = sizes[url] or 0
    if zip_path.exists() and zip_path.stat().st_size == want and want:
        print(f"zip already present ({want / 1e6:.0f} MB), skipping download")
    else:
        download(url, zip_path)

    dest = PG_DIR / "substitutions"
    files, rows = extract(zip_path, dest)
    print(f"extracted {len(files)} CSVs -> {dest}")

    manifest = {
        "url": url, "mirror_size": sizes[url],
        "zip_sha_size": zip_path.stat().st_size,
        "assays": len(files), "csv_rows": rows,
        "dir": str(dest.relative_to(REPO)),
    }
    (REPORT / "proteingym_download.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    sys.exit(main())