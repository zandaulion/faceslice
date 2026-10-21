#!/usr/bin/env python3
"""Download the three public models required by Faceslice, verifying every byte."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
FILES = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
    "selfie_multiclass.tflite": (
        "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
        "c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0",
    ),
    "depth.onnx": (
        "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/64fe43eba7f8a384b02fe3fadaa26cbba35548d8/onnx/model.onnx",
        "afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c",
    ),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    MODELS.mkdir(exist_ok=True)
    for name, (url, expected) in FILES.items():
        target = MODELS / name
        if target.exists():
            actual = digest(target)
            if actual != expected:
                raise SystemExit(f"{name}: existing file has a different SHA-256; remove it only after checking its origin")
            target.chmod(0o644)
            print(f"{name}: verified existing file")
            continue
        fd, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=MODELS)
        try:
            with os.fdopen(fd, "wb") as output, urlopen(url, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"{name}: HTTP {response.status}")
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
            actual = digest(Path(temporary))
            if actual != expected:
                raise RuntimeError(f"{name}: SHA-256 mismatch; expected {expected}, got {actual}")
            os.chmod(temporary, 0o644)
            os.replace(temporary, target)
            print(f"{name}: downloaded and verified")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


if __name__ == "__main__":
    main()
