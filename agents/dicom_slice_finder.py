"""
agents/dicom_slice_finder.py
Shared utility: locate and load DICOM files from the patient DVD.

Used by:  nexus.py, medical_vision_agent.py, medical_vision_agent_codex.py

The I: drive path is the authoritative source.
Fallback search order:
  1. I:\CTCA Heart Scan DVD 20April2026\DICOM\26052505\16080000   (Windows)
  2. Same path with forward slashes                                (WSL / Git-bash)
  3. /mnt/i/...                                                    (WSL drive mount)
  4. <project_root>/data/dicom/16080000                           (local copy)
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ── canonical search paths ────────────────────────────────────────────────────
_SERIES_SUBPATH = r"CTCA Heart Scan DVD 20April2026\DICOM\26052505\16080000"
_SERIES_SUBPATH_FWD = "CTCA Heart Scan DVD 20April2026/DICOM/26052505/16080000"

DICOM_SEARCH_ROOTS: list[str] = [
    rf"I:\{_SERIES_SUBPATH}",
    rf"I:/{_SERIES_SUBPATH_FWD}",
    rf"/mnt/i/{_SERIES_SUBPATH_FWD}",
    str(Path(__file__).parent.parent / "data" / "dicom" / "16080000"),
]

# Default 5-slice series for ZHANG, ZHIMING
DEFAULT_SLICE_UIDS: list[str] = [
    "77172526",
    "77172537",
    "77172548",
    "77172559",
    "77172570",
]

# Cardiac CT window
WINDOW_WIDTH  = 400.0
WINDOW_CENTRE = 40.0


def find_dicom_dir(extra_paths: list[str] | None = None) -> Path | None:
    """Return the first existing DICOM directory, or None."""
    paths = list(DICOM_SEARCH_ROOTS)
    if extra_paths:
        paths = extra_paths + paths
    for p in paths:
        path = Path(p)
        if path.is_dir():
            log.info("DICOM dir found: %s", path)
            return path
    log.warning("DICOM dir not found in any search path")
    return None


def dicom_to_png_b64(
    dicom_path: Path,
    ww: float = WINDOW_WIDTH,
    wc: float = WINDOW_CENTRE,
    out_size: tuple[int, int] = (660, 400),
) -> str | None:
    """
    Read one DICOM file and return a PNG data-URI string, or None on failure.

    Applies HU windowing (default: cardiac W=400 C=40).
    Resizes to out_size for consistent display.

    Requires: pydicom, numpy, Pillow
    """
    try:
        import pydicom          # type: ignore
        import numpy as np     # type: ignore
        from PIL import Image  # type: ignore

        ds  = pydicom.dcmread(str(dicom_path), force=True)
        arr = ds.pixel_array.astype(np.float32)

        slope     = float(getattr(ds, "RescaleSlope",     1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))
        arr = arr * slope + intercept

        lo  = wc - ww / 2
        hi  = wc + ww / 2
        arr = np.clip(arr, lo, hi)
        arr = ((arr - lo) / (hi - lo) * 255).astype(np.uint8)

        img = Image.fromarray(arr).convert("RGB")
        img = img.resize(out_size, Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    except ImportError as exc:
        log.warning("Missing dependency for DICOM loading: %s", exc)
        return None
    except Exception as exc:
        log.warning("Failed to load DICOM %s: %s", dicom_path, exc)
        return None


def load_slice_uris(
    slice_uids: list[str] = DEFAULT_SLICE_UIDS,
    dicom_dir: Path | None = None,
) -> dict[str, str]:
    """
    Load a list of DICOM slice UIDs → {uid: data-URI}.
    Missing or unreadable slices are silently omitted.
    """
    if dicom_dir is None:
        dicom_dir = find_dicom_dir()
    if dicom_dir is None:
        return {}

    result: dict[str, str] = {}
    for uid in slice_uids:
        candidate = dicom_dir / uid
        if not candidate.exists():
            log.debug("Slice file not found: %s", candidate)
            continue
        uri = dicom_to_png_b64(candidate)
        if uri:
            result[uid] = uri
            log.info("Loaded slice %s (%d bytes b64)", uid, len(uri))
        else:
            log.warning("Could not decode slice %s", uid)

    return result


def install_dependencies() -> bool:
    """
    Attempt to pip-install pydicom, numpy, Pillow if not present.
    Returns True if all three are now importable.
    """
    import subprocess, sys
    pkgs = []
    for pkg, imp in [("pydicom", "pydicom"), ("numpy", "numpy"), ("Pillow", "PIL")]:
        try:
            __import__(imp)
        except ImportError:
            pkgs.append(pkg)
    if not pkgs:
        return True
    log.info("Installing missing packages: %s", pkgs)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--break-system-packages"] + pkgs,
        capture_output=True,
    )
    return result.returncode == 0
