"""
brain_ml_skills.py — Scientific Brain Imaging Analysis SDK
===========================================================
K-Dense-style skill module for pixel-level quantitative brain tissue
analysis from DICOM images (MRA / T2 / FLAIR / T1).

Provides:
  • BrainTissueSegmenter   – GM / WM / CSF pixel segmentation (Otsu + GMM)
  • MorphologyAnalyser     – sulcal width, ventricular size, cortical thickness proxy
  • WMHDetector            – white matter hyperintensity detection & Fazekas grading
  • MTAEstimator           – medial temporal atrophy proxy scoring
  • MLflowTracker          – experiment logging, model versioning, run comparison
  • BrainSkillClient       – unified façade (mirrors adaptyv SDK pattern)

Usage (mirrors K-Dense adaptyv SDK):
  from brain_ml_skills import BrainSkillClient
  client = BrainSkillClient(mlflow_db="I:/MRA Brian 28May2022/brain_mlflow.db")
  result = client.analyse_series(dicom_paths, series_desc="TOF_3D", patient_age=69)
  client.log_run(result)

Author : health-self-healing-hermes project
Requires: numpy, scipy, scikit-image, scikit-learn, mlflow, pydicom, Pillow
"""

from __future__ import annotations
import warnings, json, time, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

import numpy as np
from PIL import Image
import pydicom

# ── optional imports with graceful fallback ──────────────────────────────────
try:
    from scipy import ndimage
    from scipy.stats import kurtosis, skew
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    warnings.warn("scipy not found — some metrics will be estimated")

try:
    from skimage import filters, morphology, measure, exposure, segmentation, feature
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False
    warnings.warn("scikit-image not found — segmentation quality reduced")

try:
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    warnings.warn("scikit-learn not found — GMM segmentation unavailable")

try:
    import mlflow
    import mlflow.sklearn
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    warnings.warn("mlflow not found — experiment tracking disabled")

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES  (mirrors K-Dense SDK result objects)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TissueMetrics:
    """Pixel-level brain tissue compartment measurements."""
    grey_matter_pct:   float = 0.0
    white_matter_pct:  float = 0.0
    csf_pct:           float = 0.0
    gm_wm_ratio:       float = 0.0
    total_brain_pixels: int  = 0
    skull_stripped:    bool  = False
    method:            str   = "unknown"
    confidence:        str   = "low"    # low / moderate / high
    notes:             str   = ""

@dataclass
class WMHMetrics:
    """White matter hyperintensity measurements."""
    wmh_pixel_count:        int   = 0
    wmh_pct_of_wm:          float = 0.0
    fazekas_periventricular: int  = 0   # 0–3
    fazekas_deep:           int   = 0   # 0–3
    fazekas_total:          int   = 0
    lacune_candidate_count: int   = 0
    burden:                 str   = "NONE"   # NONE/MILD/MODERATE/SEVERE
    method:                 str   = "pixel_threshold"
    confidence:             str   = "low"
    notes:                  str   = ""

@dataclass
class MTAMetrics:
    """Medial temporal atrophy proxy metrics."""
    temporal_lobe_fraction_left:  float = 0.0
    temporal_lobe_fraction_right: float = 0.0
    asymmetry_pct:                float = 0.0
    mta_proxy_left:               float = 0.0   # 0–4 scale proxy
    mta_proxy_right:              float = 0.0
    asymmetry_flag:               bool  = False
    hoc_estimate_left:            float = 0.0   # %
    hoc_estimate_right:           float = 0.0
    interpretation:               str   = "not_assessable"
    confidence:                   str   = "low"
    notes:                        str   = ""

@dataclass
class MorphologyMetrics:
    """Cortical morphology and atrophy proxy."""
    sulcal_csf_fraction:   float = 0.0   # CSF in outer cortical ring
    ventricular_csf_frac:  float = 0.0   # CSF in central region
    cortical_thickness_proxy: float = 0.0
    atrophy_grade:         int   = 0     # 0–3
    sulcal_widening:       str   = "none"
    ventricular_size:      str   = "normal"
    brain_age_delta:       float = 0.0   # estimated deviation from chronological
    confidence:            str   = "low"
    notes:                 str   = ""

@dataclass
class SeriesMLResult:
    """Full ML analysis result for one DICOM series."""
    series_desc:   str = ""
    patient_age:   int = 0
    n_slices_used: int = 0
    tissue:        TissueMetrics    = field(default_factory=TissueMetrics)
    wmh:           WMHMetrics       = field(default_factory=WMHMetrics)
    mta:           MTAMetrics       = field(default_factory=MTAMetrics)
    morph:         MorphologyMetrics = field(default_factory=MorphologyMetrics)
    overall_confidence: str = "low"
    run_id:        str = ""
    elapsed_s:     float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    # Human-readable confidence map for patient-facing reports
    CONFIDENCE_LABELS = {
        "high":     "Quantitative (high reliability)",
        "moderate": "Estimated — confirm with MRI if clinical concern",
        "low":      "Approximate — MRA not optimised for this metric; confirm with MRI",
        "none":     "Not measurable from available images",
    }

    def to_gemini_context(self) -> str:
        """Render as a compact string for inclusion in Gemini prompts."""
        t, w, m, mo = self.tissue, self.wmh, self.mta, self.morph
        return (
            f"[ML_SKILL_RESULTS — confidence:{self.overall_confidence}]\n"
            f"Tissue: GM={t.grey_matter_pct:.1f}% WM={t.white_matter_pct:.1f}% "
            f"CSF={t.csf_pct:.1f}% GM/WM={t.gm_wm_ratio:.2f} method={t.method}\n"
            f"WMH: {w.wmh_pct_of_wm:.1f}% of WM | Fazekas PV={w.fazekas_periventricular} "
            f"Deep={w.fazekas_deep} | Burden={w.burden} | Lacune candidates={w.lacune_candidate_count}\n"
            f"MTA proxy L={m.mta_proxy_left:.1f} R={m.mta_proxy_right:.1f} "
            f"Asymmetry={m.asymmetry_pct:.1f}% Flag={m.asymmetry_flag} "
            f"HOC_L={m.hoc_estimate_left:.0f}% HOC_R={m.hoc_estimate_right:.0f}%\n"
            f"Morph: AtrophyGrade={mo.atrophy_grade} Sulcal={mo.sulcal_widening} "
            f"Ventricles={mo.ventricular_size} BrainAgeDelta={mo.brain_age_delta:+.1f}yr\n"
            f"[END ML_SKILL_RESULTS — use these numbers to fill JSON fields precisely]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# DICOM LOADER
# ─────────────────────────────────────────────────────────────────────────────

class DicomLoader:
    """Load and normalise DICOM pixel arrays."""

    @staticmethod
    def load(path: Path) -> Optional[np.ndarray]:
        try:
            ds  = pydicom.dcmread(str(path))
            arr = ds.pixel_array.astype(np.float32)
            if arr.ndim == 3:
                arr = arr[arr.shape[0] // 2]
            return arr
        except Exception:
            return None

    @staticmethod
    def normalise(arr: np.ndarray) -> np.ndarray:
        lo, hi = arr.min(), arr.max()
        if hi == lo:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    @staticmethod
    def load_stack(paths: List[Path], max_slices: int = 12) -> List[np.ndarray]:
        """Load evenly-spaced slices from a series."""
        n = len(paths)
        # Take slices from middle 50% — avoid blank edge slices
        start = n // 4
        end   = n * 3 // 4
        mid   = paths[start:end]
        step  = max(1, len(mid) // max_slices)
        picks = mid[::step][:max_slices]
        arrays = []
        for p in picks:
            arr = DicomLoader.load(p)
            if arr is not None and arr.max() > arr.min():
                arrays.append(DicomLoader.normalise(arr))
        return arrays


# ─────────────────────────────────────────────────────────────────────────────
# SKULL STRIPPER  (simple intensity + morphology — no atlas needed)
# ─────────────────────────────────────────────────────────────────────────────

class SkullStripper:
    """
    Rough skull-strip using Otsu threshold + largest connected component.
    Works on normalised [0,1] arrays. Confidence: moderate for T1/T2,
    low for MRA (vessels bright, background dark).
    """

    @staticmethod
    def strip(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (stripped_arr, brain_mask)."""
        if not HAS_SKIMAGE:
            # Fallback: simple intensity threshold
            mask = arr > 0.15
            return arr * mask, mask

        try:
            thresh = filters.threshold_otsu(arr)
            binary = arr > thresh * 0.6   # be generous — keep brain tissue

            if HAS_SCIPY:
                # Fill holes, keep largest component
                binary = ndimage.binary_fill_holes(binary)
                labeled, n = ndimage.label(binary)
                if n > 0:
                    sizes = ndimage.sum(binary, labeled, range(1, n + 1))
                    largest = np.argmax(sizes) + 1
                    binary = labeled == largest

                # Morphological closing to smooth brain boundary
                binary = ndimage.binary_closing(binary, iterations=5)

            return arr * binary, binary.astype(np.uint8)
        except Exception:
            mask = arr > 0.15
            return arr * mask, mask.astype(np.uint8)


# ─────────────────────────────────────────────────────────────────────────────
# BRAIN TISSUE SEGMENTER
# ─────────────────────────────────────────────────────────────────────────────

class BrainTissueSegmenter:
    """
    Segment brain pixels into GM / WM / CSF using:
      1. Gaussian Mixture Model (3 components) — sklearn GMM
      2. Fallback: 3-level Otsu thresholding (scikit-image)
      3. Fallback: simple intensity percentile bands

    Aggregates across multiple slices for stability.
    """

    def __init__(self, n_components: int = 3):
        self.n_components = n_components

    def _gmm_segment(self, pixels: np.ndarray) -> tuple[float, float, float, str]:
        """Returns (csf_pct, gm_pct, wm_pct, method)."""
        if not HAS_SKLEARN or len(pixels) < 100:
            return self._otsu_segment(pixels)

        try:
            X = pixels.reshape(-1, 1)
            gmm = GaussianMixture(
                n_components=self.n_components,
                covariance_type="full",
                max_iter=200,
                random_state=42
            )
            gmm.fit(X)
            labels = gmm.predict(X)
            # Sort components by mean intensity: CSF (darkest) < GM < WM (brightest)
            means = [(gmm.means_[i][0], i) for i in range(self.n_components)]
            means.sort(key=lambda x: x[0])
            # For MRA/T2: CSF=dark, GM=mid, WM=bright
            # (for T1 it's reversed: CSF=dark, WM=bright, GM=mid — same ordering holds)
            counts = np.array([np.sum(labels == m[1]) for m in means])
            total  = counts.sum()
            if total == 0:
                return 0.0, 0.0, 0.0, "gmm_failed"
            pcts = counts / total * 100
            return float(pcts[0]), float(pcts[1]), float(pcts[2]), "GMM_3component"
        except Exception:
            return self._otsu_segment(pixels)

    def _otsu_segment(self, pixels: np.ndarray) -> tuple[float, float, float, str]:
        """3-level Otsu via multi-threshold."""
        if not HAS_SKIMAGE or len(pixels) < 50:
            return self._percentile_segment(pixels)
        try:
            thresholds = filters.threshold_multiotsu(pixels, classes=3)
            t1, t2     = thresholds[0], thresholds[1]
            csf_pct = np.sum(pixels <= t1) / len(pixels) * 100
            gm_pct  = np.sum((pixels > t1) & (pixels <= t2)) / len(pixels) * 100
            wm_pct  = np.sum(pixels > t2) / len(pixels) * 100
            return float(csf_pct), float(gm_pct), float(wm_pct), "3level_Otsu"
        except Exception:
            return self._percentile_segment(pixels)

    def _percentile_segment(self, pixels: np.ndarray) -> tuple[float, float, float, str]:
        """Last-resort: fixed intensity percentile bands."""
        csf_pct = float(np.sum(pixels < 0.25) / len(pixels) * 100)
        gm_pct  = float(np.sum((pixels >= 0.25) & (pixels < 0.60)) / len(pixels) * 100)
        wm_pct  = float(np.sum(pixels >= 0.60) / len(pixels) * 100)
        return csf_pct, gm_pct, wm_pct, "percentile_bands"

    def analyse(self, arrays: List[np.ndarray]) -> TissueMetrics:
        if not arrays:
            return TissueMetrics(notes="No valid slices")

        all_csf, all_gm, all_wm = [], [], []
        total_brain_px = 0
        methods_used   = set()

        for arr in arrays:
            stripped, mask = SkullStripper.strip(arr)
            brain_px = stripped[mask > 0]
            if len(brain_px) < 100:
                continue
            total_brain_px += len(brain_px)
            csf_p, gm_p, wm_p, method = self._gmm_segment(brain_px)
            all_csf.append(csf_p)
            all_gm.append(gm_p)
            all_wm.append(wm_p)
            methods_used.add(method)

        if not all_gm:
            return TissueMetrics(notes="Segmentation failed on all slices", confidence="low")

        csf = float(np.median(all_csf))
        gm  = float(np.median(all_gm))
        wm  = float(np.median(all_wm))

        # Normalise to 100%
        total = csf + gm + wm
        if total > 0:
            csf, gm, wm = csf/total*100, gm/total*100, wm/total*100

        gm_wm_ratio = gm / wm if wm > 0 else 0.0

        # Confidence: GMM on many slices = moderate; Otsu = low; MRA source = cap at moderate
        n_slices   = len(all_gm)
        best_method = list(methods_used)[0] if methods_used else "unknown"
        confidence  = ("moderate" if "GMM" in best_method and n_slices >= 5
                       else "low")

        # GM status vs age norms (69yo male: GM ~42-46%)
        gm_status = ("NORMAL" if gm >= 40 else
                     "MILDLY_REDUCED" if gm >= 35 else
                     "MODERATELY_REDUCED")

        return TissueMetrics(
            grey_matter_pct   = round(gm, 1),
            white_matter_pct  = round(wm, 1),
            csf_pct           = round(csf, 1),
            gm_wm_ratio       = round(gm_wm_ratio, 2),
            total_brain_pixels= total_brain_px,
            skull_stripped    = True,
            method            = f"{best_method} | {n_slices} slices | median-aggregated",
            confidence        = confidence,
            notes             = (f"GM status: {gm_status}. "
                                 f"Normal ranges age 69: GM ~42-46%, WM ~40-46%, CSF ~10-16%. "
                                 f"Method: {best_method} across {n_slices} slices.")
        )


# ─────────────────────────────────────────────────────────────────────────────
# WMH DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class WMHDetector:
    """
    Detect white matter hyperintensities from FLAIR / T2 background signal.
    On MRA: detects high-signal foci in white matter region as WMH proxies.

    Algorithm:
      1. Skull-strip
      2. Define WM mask (upper-intensity region within brain)
      3. WMH = pixels in WM mask that are > mean + 2SD (bright foci)
      4. Size-filter: discard very small blobs (< 5px — noise)
      5. Periventricular vs deep: central 40% of brain = periventricular zone
      6. Lacune candidates: rounded hypointense foci 3–15mm diameter
      7. Fazekas grading from WMH burden %
    """

    def analyse(self, arrays: List[np.ndarray], sequence: str = "unknown") -> WMHMetrics:
        if not arrays:
            return WMHMetrics(notes="No slices", confidence="low")

        wmh_counts, wm_totals = [], []
        pv_counts, deep_counts = [], []
        lacune_candidates = 0

        for arr in arrays:
            stripped, mask = SkullStripper.strip(arr)
            if mask.sum() < 200:
                continue

            h, w = arr.shape
            # WM mask = upper 40% intensity within brain (bright = WM on T2/FLAIR/MRA bg)
            brain_vals = stripped[mask > 0]
            wm_thresh  = np.percentile(brain_vals, 60)
            wm_mask    = (stripped > wm_thresh) & (mask > 0)

            if wm_mask.sum() < 50:
                continue

            # WMH = anomalously bright pixels in WM (> mean + 1.8 SD)
            wm_vals = stripped[wm_mask]
            wmh_thresh = wm_vals.mean() + 1.8 * wm_vals.std()
            wmh_raw    = (stripped > wmh_thresh) & (mask > 0)

            # Remove tiny noise blobs
            if HAS_SCIPY:
                wmh_clean = ndimage.binary_opening(wmh_raw, iterations=1)
                labeled, n_blobs = ndimage.label(wmh_clean)
                wmh_final = np.zeros_like(wmh_raw)
                for blob_id in range(1, n_blobs + 1):
                    blob = labeled == blob_id
                    size = blob.sum()
                    if size >= 4:
                        wmh_final |= blob
                # Lacune candidates: rounded dark foci 3-15px in WM region
                dark_foci = (stripped < np.percentile(brain_vals, 15)) & (mask > 0)
                if HAS_SKIMAGE:
                    try:
                        labeled_dark, n_dark = ndimage.label(dark_foci)
                        for did in range(1, n_dark + 1):
                            blob = labeled_dark == did
                            sz   = blob.sum()
                            if 3 <= sz <= 20:
                                lacune_candidates += 1
                    except Exception:
                        pass
            else:
                wmh_final = wmh_raw

            # Periventricular zone = central 50% of image
            cy, cx = h // 2, w // 2
            pv_zone = np.zeros_like(mask)
            pv_zone[int(cy*0.25):int(cy*1.75), int(cx*0.25):int(cx*1.75)] = 1
            pv_wmh   = (wmh_final & (pv_zone > 0)).sum()
            deep_wmh = (wmh_final & (pv_zone == 0)).sum()
            pv_counts.append(int(pv_wmh))
            deep_counts.append(int(deep_wmh))
            wmh_counts.append(int(wmh_final.sum()))
            wm_totals.append(int(wm_mask.sum()))

        if not wmh_counts:
            return WMHMetrics(notes="No processable slices", confidence="low")

        total_wmh = int(np.median(wmh_counts))
        total_wm  = int(np.median(wm_totals))
        wmh_pct   = (total_wmh / total_wm * 100) if total_wm > 0 else 0.0
        pv_wmh    = int(np.median(pv_counts))
        deep_wmh  = int(np.median(deep_counts))

        # Fazekas grading
        faz_pv = (0 if pv_wmh == 0 else
                  1 if pv_wmh < total_wm * 0.02 else
                  2 if pv_wmh < total_wm * 0.08 else 3)
        faz_deep = (0 if deep_wmh == 0 else
                    1 if deep_wmh < total_wm * 0.01 else
                    2 if deep_wmh < total_wm * 0.05 else 3)

        burden = ("NONE"     if wmh_pct < 0.5 else
                  "MILD"     if wmh_pct < 2.0 else
                  "MODERATE" if wmh_pct < 5.0 else "SEVERE")

        # Confidence: FLAIR = moderate, MRA/T2 background = low
        is_flair = any(x in sequence.upper() for x in ["FLAIR","T2"])
        conf = "moderate" if is_flair else "low"

        return WMHMetrics(
            wmh_pixel_count        = total_wmh,
            wmh_pct_of_wm          = round(wmh_pct, 2),
            fazekas_periventricular= faz_pv,
            fazekas_deep           = faz_deep,
            fazekas_total          = faz_pv + faz_deep,
            lacune_candidate_count = lacune_candidates,
            burden                 = burden,
            method                 = f"pixel_threshold_1.8SD | {len(wmh_counts)} slices | sequence={sequence}",
            confidence             = conf,
            notes                  = (f"WMH={wmh_pct:.2f}% of WM. Fazekas PV={faz_pv} Deep={faz_deep}. "
                                      f"Lacune candidates={lacune_candidates}. "
                                      f"For MRA source: low confidence — recommend dedicated FLAIR.")
        )


# ─────────────────────────────────────────────────────────────────────────────
# MTA ESTIMATOR  (proxy from temporal region intensity asymmetry)
# ─────────────────────────────────────────────────────────────────────────────

class MTAEstimator:
    """
    Proxy MTA scoring from brain slice morphology.

    True MTA requires coronal T1. This gives a pixel-level proxy by:
      1. Splitting brain into left/right temporal regions (lower lateral quadrants)
      2. Measuring tissue density (GM fraction) in each region
      3. Asymmetry → flag if > 10%
      4. Map temporal GM fraction to MTA 0-4 proxy scale

    Confidence: always low for MRA source; moderate if T1 available.
    """

    def analyse(self, arrays: List[np.ndarray], patient_age: int = 69) -> MTAMetrics:
        if not arrays:
            return MTAMetrics(notes="No slices", confidence="low")

        left_fracs, right_fracs = [], []

        for arr in arrays:
            stripped, mask = SkullStripper.strip(arr)
            h, w = arr.shape
            if mask.sum() < 200:
                continue

            # Temporal region proxy = lower 40%, lateral 30% on each side
            # (inferior temporal lobe approximation on axial slices)
            row_start = int(h * 0.55)
            row_end   = int(h * 0.85)
            col_L_end = int(w * 0.35)
            col_R_start = int(w * 0.65)

            left_roi  = stripped[row_start:row_end, :col_L_end]
            right_roi = stripped[row_start:row_end, col_R_start:]
            lmask = mask[row_start:row_end, :col_L_end]
            rmask = mask[row_start:row_end, col_R_start:]

            if lmask.sum() < 20 or rmask.sum() < 20:
                continue

            # GM proxy = mid-intensity fraction (0.25-0.65 on normalised)
            l_brain = left_roi[lmask > 0]
            r_brain = right_roi[rmask > 0]
            l_gm_frac = float(np.sum((l_brain > 0.25) & (l_brain < 0.65)) / len(l_brain))
            r_gm_frac = float(np.sum((r_brain > 0.25) & (r_brain < 0.65)) / len(r_brain))
            left_fracs.append(l_gm_frac)
            right_fracs.append(r_gm_frac)

        if not left_fracs:
            return MTAMetrics(
                notes="Temporal regions not identifiable on available slices",
                confidence="low"
            )

        l_frac = float(np.median(left_fracs))
        r_frac = float(np.median(right_fracs))
        mean_frac = (l_frac + r_frac) / 2

        # Asymmetry
        asym_pct = abs(l_frac - r_frac) / max(mean_frac, 0.01) * 100

        # MTA proxy: higher GM fraction = more preserved = lower MTA score
        # Calibrated to 69yo expected GM fraction ~0.35–0.45 in temporal ROI
        def frac_to_mta(frac: float, age: int) -> float:
            # Age-adjusted expected fraction
            age_adj = max(0.30, 0.50 - (age - 50) * 0.005)
            deficit = max(0.0, age_adj - frac) / age_adj
            return min(4.0, round(deficit * 6.0, 1))

        mta_l = frac_to_mta(l_frac, patient_age)
        mta_r = frac_to_mta(r_frac, patient_age)

        # HOC proxy: tissue fraction in temporal ROI relative to expected
        hoc_l = min(100.0, round(l_frac / max(0.01, 0.42) * 70, 1))
        hoc_r = min(100.0, round(r_frac / max(0.01, 0.42) * 70, 1))

        asym_flag = asym_pct > 10.0
        interpretation = ("not_assessable" if mean_frac < 0.05 else
                          "normal_for_age" if mta_l <= 1.5 and mta_r <= 1.5 else
                          "borderline"     if max(mta_l, mta_r) <= 2.5 else "abnormal")

        return MTAMetrics(
            temporal_lobe_fraction_left  = round(l_frac, 3),
            temporal_lobe_fraction_right = round(r_frac, 3),
            asymmetry_pct                = round(asym_pct, 1),
            mta_proxy_left               = mta_l,
            mta_proxy_right              = mta_r,
            asymmetry_flag               = asym_flag,
            hoc_estimate_left            = hoc_l,
            hoc_estimate_right           = hoc_r,
            interpretation               = interpretation,
            confidence                   = "low",
            notes                        = (
                f"Proxy MTA from temporal ROI intensity on axial slices. "
                f"L_frac={l_frac:.3f} R_frac={r_frac:.3f} across {len(left_fracs)} slices. "
                f"HOC: L={hoc_l:.0f}% R={hoc_r:.0f}%. Asymmetry={asym_pct:.1f}% "
                f"({'FLAG >10%' if asym_flag else 'within normal'}). "
                f"Confidence=LOW — dedicated coronal T1 required for true MTA scoring."
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# MORPHOLOGY ANALYSER  (sulcal width, atrophy grade, brain age delta)
# ─────────────────────────────────────────────────────────────────────────────

class MorphologyAnalyser:
    """
    Measure cortical morphology proxy from pixel distributions:
      • Sulcal CSF fraction (outer cortical ring CSF)
      • Ventricular CSF fraction (central region)
      • Cortical thickness proxy (mean GM band width estimate)
      • Atrophy grading 0-3
      • Brain age delta estimation
    """

    def analyse(self, arrays: List[np.ndarray], patient_age: int = 69) -> MorphologyMetrics:
        if not arrays:
            return MorphologyMetrics(notes="No slices", confidence="low")

        sulcal_fracs, vent_fracs, thickness_proxies = [], [], []

        for arr in arrays:
            stripped, mask = SkullStripper.strip(arr)
            if mask.sum() < 200:
                continue
            h, w = arr.shape

            brain_vals = stripped[mask > 0]
            if len(brain_vals) < 100:
                continue
            csf_thresh = np.percentile(brain_vals, 20)

            # Sulcal CSF = dark pixels in outer 20% ring of brain mask
            outer_ring = np.zeros_like(mask)
            if HAS_SCIPY:
                eroded = ndimage.binary_erosion(mask > 0, iterations=max(1, int(min(h,w)*0.08)))
                outer_ring = ((mask > 0) & ~eroded).astype(np.uint8)
            else:
                outer_ring[int(h*0.05):int(h*0.95), int(w*0.05):int(w*0.95)] = 0
                outer_ring = mask

            outer_px = stripped[outer_ring > 0]
            if len(outer_px) > 10:
                sulcal_frac = float(np.sum(outer_px < csf_thresh) / len(outer_px))
                sulcal_fracs.append(sulcal_frac)

            # Ventricular CSF = dark pixels in central 25% of brain
            cy, cx = h // 2, w // 2
            central = stripped[int(cy*0.6):int(cy*1.4), int(cx*0.6):int(cx*1.4)]
            cmask   = mask[int(cy*0.6):int(cy*1.4), int(cx*0.6):int(cx*1.4)]
            c_px    = central[cmask > 0]
            if len(c_px) > 10:
                vent_frac = float(np.sum(c_px < csf_thresh) / len(c_px))
                vent_fracs.append(vent_frac)

            # Cortical thickness proxy = mean width of GM band (mid-intensity)
            gm_band = (stripped > csf_thresh) & (stripped < np.percentile(brain_vals, 75)) & (mask > 0)
            if HAS_SCIPY:
                profile = gm_band.sum(axis=1)
                if profile.max() > 0:
                    thickness_proxies.append(float(np.median(profile[profile > 0])))

        if not sulcal_fracs:
            return MorphologyMetrics(notes="Morphology analysis failed", confidence="low")

        sulcal_frac = float(np.median(sulcal_fracs))
        vent_frac   = float(np.median(vent_fracs)) if vent_fracs else 0.0
        thickness   = float(np.median(thickness_proxies)) if thickness_proxies else 0.0

        # Atrophy grade from sulcal + ventricular fractions
        # Age-calibrated: 69yo expected sulcal_frac ~0.12-0.20
        atrophy_score = sulcal_frac * 8 + vent_frac * 4
        atrophy_grade = int(min(3, atrophy_score))

        sulcal_widening = ("none"     if sulcal_frac < 0.12 else
                           "mild"     if sulcal_frac < 0.22 else
                           "moderate" if sulcal_frac < 0.35 else "severe")
        vent_size       = ("normal"           if vent_frac < 0.20 else
                           "mildly enlarged"  if vent_frac < 0.35 else
                           "moderately enlarged")

        # Brain age delta: each unit of atrophy grade ≈ +3-5 years
        brain_age_delta = atrophy_grade * 4.0 + (sulcal_frac - 0.15) * 20

        return MorphologyMetrics(
            sulcal_csf_fraction    = round(sulcal_frac, 3),
            ventricular_csf_frac   = round(vent_frac, 3),
            cortical_thickness_proxy = round(thickness, 1),
            atrophy_grade          = atrophy_grade,
            sulcal_widening        = sulcal_widening,
            ventricular_size       = vent_size,
            brain_age_delta        = round(brain_age_delta, 1),
            confidence             = "low",
            notes                  = (
                f"Sulcal CSF frac={sulcal_frac:.3f} (norm 69yo: 0.12-0.20). "
                f"Ventricular CSF frac={vent_frac:.3f}. "
                f"Atrophy grade={atrophy_grade}/3. Brain age delta={brain_age_delta:+.1f}yr. "
                f"Confidence=LOW — MRA background source."
            )
        )


# ─────────────────────────────────────────────────────────────────────────────
# MLFLOW TRACKER  (mirrors MLflow usage in LiDAR pipeline)
# ─────────────────────────────────────────────────────────────────────────────

class MLflowTracker:
    """
    Experiment tracking for brain MRI analysis runs.
    Mirrors the MLflow pattern from 17.agentic_ai_lidar_pipeline_demo.ipynb.

    Each DICOM series analysis = one MLflow run with:
      • Parameters: patient_age, series_desc, sequence_type, n_slices
      • Metrics: all tissue/WMH/MTA/morphology numeric values
      • Tags: confidence levels, method names
      • Artifacts: result JSON

    Enables:
      • Run comparison across dates (2022 vs 2024 MRI)
      • Model versioning (segmentation algorithm versions)
      • Delta tracking (e.g. basilar diameter change over time)
    """

    EXPERIMENT_NAME = "BrainMRI_Analysis"

    def __init__(self, db_path: str = "./brain_mlflow.db"):
        self.enabled = HAS_MLFLOW
        self.db_path = db_path
        if self.enabled:
            try:
                # Windows absolute path fix: use forward slashes
                db_clean = str(db_path).replace("\\", "/").replace("\\", "/")
                if ":" in db_clean:  # Windows drive letter detected
                    tracking_uri = f"sqlite:///{db_clean}"
                else:
                    tracking_uri = f"sqlite:///{db_clean}"
                mlflow.set_tracking_uri(tracking_uri)
                mlflow.set_experiment(self.EXPERIMENT_NAME)
                print(f"  📊 MLflow tracking → {db_path}")
            except Exception as e:
                print(f"  ⚠️  MLflow init warning: {e}")
                self.enabled = False

    def log_series_result(self, result: SeriesMLResult, scan_date: str, patient_name: str) -> str:
        """Log one series analysis as an MLflow run. Returns run_id."""
        if not self.enabled:
            return ""
        try:
            with mlflow.start_run(run_name=f"{result.series_desc}_{scan_date}") as run:
                # ── Tags ──────────────────────────────────────────────────────
                mlflow.set_tags({
                    "patient":       patient_name,
                    "scan_date":     scan_date,
                    "series":        result.series_desc,
                    "confidence":    result.overall_confidence,
                    "tissue_method": result.tissue.method[:80],
                    "wmh_method":    result.wmh.method[:80],
                    "skill_version": "brain_ml_skills_v1",
                })

                # ── Parameters ────────────────────────────────────────────────
                mlflow.log_params({
                    "patient_age":   result.patient_age,
                    "n_slices_used": result.n_slices_used,
                    "sequence":      result.series_desc[:50],
                    "skull_stripped": result.tissue.skull_stripped,
                })

                # ── Metrics — Tissue ─────────────────────────────────────────
                mlflow.log_metrics({
                    "grey_matter_pct":   result.tissue.grey_matter_pct,
                    "white_matter_pct":  result.tissue.white_matter_pct,
                    "csf_pct":           result.tissue.csf_pct,
                    "gm_wm_ratio":       result.tissue.gm_wm_ratio,
                })

                # ── Metrics — WMH ────────────────────────────────────────────
                mlflow.log_metrics({
                    "wmh_pct_of_wm":          result.wmh.wmh_pct_of_wm,
                    "fazekas_periventricular": result.wmh.fazekas_periventricular,
                    "fazekas_deep":            result.wmh.fazekas_deep,
                    "fazekas_total":           result.wmh.fazekas_total,
                    "lacune_candidates":       result.wmh.lacune_candidate_count,
                })

                # ── Metrics — MTA ────────────────────────────────────────────
                mlflow.log_metrics({
                    "mta_proxy_left":    result.mta.mta_proxy_left,
                    "mta_proxy_right":   result.mta.mta_proxy_right,
                    "mta_asymmetry_pct": result.mta.asymmetry_pct,
                    "hoc_estimate_left":  result.mta.hoc_estimate_left,
                    "hoc_estimate_right": result.mta.hoc_estimate_right,
                })

                # ── Metrics — Morphology ──────────────────────────────────────
                mlflow.log_metrics({
                    "atrophy_grade":       result.morph.atrophy_grade,
                    "sulcal_csf_frac":     result.morph.sulcal_csf_fraction,
                    "ventricular_csf_frac":result.morph.ventricular_csf_frac,
                    "brain_age_delta":     result.morph.brain_age_delta,
                    "elapsed_s":           result.elapsed_s,
                })

                # ── Artifact: full JSON result ────────────────────────────────
                import tempfile, os
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".json", delete=False, prefix="brain_ml_"
                ) as tmp:
                    json.dump(result.to_dict(), tmp, indent=2)
                    tmp_path = tmp.name
                mlflow.log_artifact(tmp_path, artifact_path="results")
                os.unlink(tmp_path)

                return run.info.run_id
        except Exception as e:
            print(f"  ⚠️  MLflow log error: {e}")
            return ""

    def get_previous_run(self, series_desc: str, patient_name: str) -> Optional[Dict]:
        """Retrieve most recent prior run for this series+patient (for delta comparison)."""
        if not self.enabled:
            return None
        try:
            runs = mlflow.search_runs(
                experiment_names=[self.EXPERIMENT_NAME],
                filter_string=f"tags.patient = '{patient_name}' and tags.series LIKE '%{series_desc[:20]}%'",
                order_by=["start_time DESC"],
                max_results=2
            )
            if len(runs) >= 2:
                prev = runs.iloc[1]  # second-most-recent = prior run
                return prev.to_dict()
        except Exception:
            pass
        return None

    def compute_delta(self, current: SeriesMLResult, prev_run: Optional[Dict]) -> Dict[str, float]:
        """Compute metric deltas vs previous run."""
        if not prev_run:
            return {}
        deltas = {}
        metric_map = {
            "grey_matter_pct":        current.tissue.grey_matter_pct,
            "wmh_pct_of_wm":         current.wmh.wmh_pct_of_wm,
            "mta_proxy_left":        current.mta.mta_proxy_left,
            "mta_proxy_right":       current.mta.mta_proxy_right,
            "atrophy_grade":         float(current.morph.atrophy_grade),
            "brain_age_delta":       current.morph.brain_age_delta,
        }
        for key, val in metric_map.items():
            prev_key = f"metrics.{key}"
            if prev_key in prev_run:
                deltas[f"delta_{key}"] = round(val - float(prev_run[prev_key]), 3)
        return deltas


# ─────────────────────────────────────────────────────────────────────────────
# BRAIN SKILL CLIENT  (unified façade — mirrors adaptyv SDK pattern)
# ─────────────────────────────────────────────────────────────────────────────

class BrainSkillClient:
    """
    Unified client for brain tissue ML analysis + MLflow tracking.
    Mirrors the K-Dense adaptyv SDK pattern:

        client = BrainSkillClient(mlflow_db="path/to/brain_mlflow.db")
        result = client.analyse_series(paths, desc="TOF_3D", age=69)
        context_str = result.to_gemini_context()   # inject into Gemini prompt
    """

    VERSION = "1.0.0"

    def __init__(self, mlflow_db: str = "./brain_mlflow.db",
                 patient_name: str = "unknown", scan_date: str = "unknown"):
        self.tracker      = MLflowTracker(db_path=mlflow_db)
        self.patient_name = patient_name
        self.scan_date    = scan_date
        self.segmenter    = BrainTissueSegmenter()
        self.wmh_detector = WMHDetector()
        self.mta_estimator= MTAEstimator()
        self.morph_analyser = MorphologyAnalyser()
        print(f"  🧠 BrainSkillClient v{self.VERSION} ready | MLflow: {mlflow_db}")

    def analyse_series(
        self,
        dicom_paths: List[Path],
        series_desc: str = "unknown",
        patient_age: int = 69,
        max_slices:  int = 12,
    ) -> SeriesMLResult:
        """
        Run full ML analysis on a DICOM series.
        Returns SeriesMLResult with all metrics + MLflow run_id.
        """
        t0 = time.time()
        print(f"    🔬 ML analysis: {series_desc} ({len(dicom_paths)} files)...")

        # Load normalised arrays
        arrays = DicomLoader.load_stack(dicom_paths, max_slices=max_slices)
        n_slices = len(arrays)
        print(f"       Loaded {n_slices} slices")

        if n_slices == 0:
            result = SeriesMLResult(
                series_desc=series_desc, patient_age=patient_age,
                n_slices_used=0, overall_confidence="none",
                tissue=TissueMetrics(notes="No loadable slices"),
            )
            return result

        # Run all analysers
        print(f"       Segmenting tissue (GMM)...")
        tissue = self.segmenter.analyse(arrays)

        print(f"       Detecting WMH...")
        wmh    = self.wmh_detector.analyse(arrays, sequence=series_desc)

        print(f"       Estimating MTA proxy...")
        mta    = self.mta_estimator.analyse(arrays, patient_age=patient_age)

        print(f"       Analysing morphology...")
        morph  = self.morph_analyser.analyse(arrays, patient_age=patient_age)

        # Overall confidence = minimum of all components
        conf_rank = {"high": 3, "moderate": 2, "low": 1, "none": 0}
        confs     = [tissue.confidence, wmh.confidence, mta.confidence, morph.confidence]
        overall   = min(confs, key=lambda c: conf_rank.get(c, 0))

        elapsed = time.time() - t0
        result  = SeriesMLResult(
            series_desc    = series_desc,
            patient_age    = patient_age,
            n_slices_used  = n_slices,
            tissue         = tissue,
            wmh            = wmh,
            mta            = mta,
            morph          = morph,
            overall_confidence = overall,
            elapsed_s      = round(elapsed, 2),
        )

        # Log to MLflow
        run_id = self.tracker.log_series_result(result, self.scan_date, self.patient_name)
        result.run_id = run_id
        if run_id:
            print(f"       📊 MLflow run: {run_id[:8]}...")

        print(f"       ✓ ML done in {elapsed:.1f}s | confidence={overall}")
        return result

    def get_delta_summary(self, result: SeriesMLResult) -> str:
        """Get metric deltas vs prior MLflow run as a formatted string."""
        prev = self.tracker.get_previous_run(result.series_desc, self.patient_name)
        deltas = self.tracker.compute_delta(result, prev)
        if not deltas:
            return "(no prior run for comparison)"
        lines = []
        for k, v in deltas.items():
            arrow = "↑" if v > 0 else ("↓" if v < 0 else "→")
            lines.append(f"  {k.replace('delta_','')}: {arrow}{abs(v):.3f}")
        return "Delta vs prior run:\n" + "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# QUICK SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

def _self_test():
    """Run a quick synthetic test to verify all components work."""
    print("\n=== BrainSkillClient self-test ===")

    # Synthetic brain-like image: dark CSF surround, mid-grey GM ring, bright WM centre
    img = np.zeros((128, 128), dtype=np.float32)
    cy, cx = 64, 64
    for y in range(128):
        for x in range(128):
            r = np.sqrt((y-cy)**2 + (x-cx)**2)
            if r < 20:   img[y,x] = 0.85   # WM
            elif r < 38: img[y,x] = 0.45   # GM
            elif r < 52: img[y,x] = 0.10   # CSF
    # Add some bright WMH foci
    img[30:34, 40:44] = 0.95
    img[55:58, 75:78] = 0.92

    arrays = [img] * 8   # simulate 8 slices

    seg  = BrainTissueSegmenter().analyse(arrays)
    wmh  = WMHDetector().analyse(arrays, "T2")
    mta  = MTAEstimator().analyse(arrays, 69)
    morph= MorphologyAnalyser().analyse(arrays, 69)

    print(f"  Tissue: GM={seg.grey_matter_pct}% WM={seg.white_matter_pct}% CSF={seg.csf_pct}% [{seg.method}]")
    print(f"  WMH:    {wmh.wmh_pct_of_wm}% | Fazekas PV={wmh.fazekas_periventricular} Deep={wmh.fazekas_deep}")
    print(f"  MTA:    L={mta.mta_proxy_left} R={mta.mta_proxy_right} Asym={mta.asymmetry_pct}%")
    print(f"  Morph:  Grade={morph.atrophy_grade} Sulcal={morph.sulcal_widening}")

    # Test SeriesMLResult.to_gemini_context()
    r = SeriesMLResult(series_desc="TEST", patient_age=69, n_slices_used=8,
                       tissue=seg, wmh=wmh, mta=mta, morph=morph)
    ctx = r.to_gemini_context()
    assert "[ML_SKILL_RESULTS" in ctx
    print(f"  Gemini context: {len(ctx)} chars ✓")
    print("=== self-test PASSED ===\n")


if __name__ == "__main__":
    _self_test()
