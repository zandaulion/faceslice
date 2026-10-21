#!/usr/bin/env python3
"""Build the deterministic, model-free Faceslice self-hosting archive."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
VERSION = "v0.1.0"
PREFIX = f"Faceslice-{VERSION}/"
NAME = f"Faceslice-{VERSION}-self-host.zip"
FILES = [ROOT / name for name in (
    "README.md", "LICENSE", "SECURITY.md", "THIRD_PARTY_NOTICES.md", "requirements.txt",
    "deploy/Containerfile", "examples/synthetic-portrait.png",
    "scripts/download-models.py", "scripts/package-release.py",
    "server/app.py", "server/auth.py", "server/db.py", "server/dxf.py",
    "server/pipeline.py", "server/profil.py", "server/render.py", "server/serve-sw.js",
    "server/slicer.py", "web/app.css", "web/app.js", "web/bust.html",
    "web/icons/icon-192.png", "web/icons/icon-512.png",
    "web/icons/icon-maskable.png", "web/icons/icon-maskable.svg",
    "web/icons/icon.svg", "web/index.html", "web/manifest.webmanifest",
    "web/pwa-update.js", "web/sw-update.js", "web/sw.js",
)]


def write_member(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (0o644 << 16)
    archive.writestr(info, content, compresslevel=9)


def main() -> None:
    output = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else ROOT / "dist"
    output.mkdir(parents=True, exist_ok=True)
    members: dict[str, str] = {}
    payload: dict[str, bytes] = {}
    for path in FILES:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"required release file missing or unsafe: {path.relative_to(ROOT)}")
        name = path.relative_to(ROOT).as_posix()
        if name.startswith("models/") or name.startswith("data/"):
            raise RuntimeError(f"private or external data selected: {name}")
        content = path.read_bytes()
        payload[name] = content
        members[name] = hashlib.sha256(content).hexdigest()
    if len(payload) < 15:
        raise RuntimeError("release payload is incomplete")
    manifest = json.dumps({"version": VERSION, "files": members}, indent=2, ensure_ascii=False).encode() + b"\n"
    target = output / NAME
    with ZipFile(target, "w") as archive:
        for name in sorted(payload):
            write_member(archive, PREFIX + name, payload[name])
        write_member(archive, PREFIX + "RELEASE-MANIFEST.json", manifest)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {NAME}\n")
    print(f"{target} ({target.stat().st_size} bytes, {len(payload) + 1} files)")
    print(digest)


if __name__ == "__main__":
    main()
