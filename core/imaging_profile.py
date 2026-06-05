"""
core/imaging_profile.py
Per-user DICOM imaging profile registry.

Each user account is mapped to their own:
  - patient name / ID
  - DICOM directory path(s)
  - slice UIDs to display
  - scan metadata (study, date, scanner, referring doctor)

The profile is looked up at runtime using the authenticated username
(st.session_state["username"]) so no user ever sees another user's images.

HOW TO ADD A NEW USER:
  Add an entry to USER_IMAGING_PROFILES below.
  The key is the username exactly as stored in your auth DB.
  Paths can be Windows drive paths, WSL mounts, or relative project paths.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Profile dataclass
# ---------------------------------------------------------------------------
@dataclass
class ImagingProfile:
    # Patient / study info (displayed in the viewer header)
    patient_name:   str = "Unknown Patient"
    patient_id:     str = "—"
    patient_dob:    str = "—"
    patient_sex:    str = "—"
    study_desc:     str = "—"
    study_date:     str = "—"
    heart_rate:     str = "—"
    scanner:        str = "—"
    facility:       str = "—"
    referring_dr:   str = "—"
    protocol:       str = "—"
    window_str:     str = "W: 400 / C: 40"
    mAs:            str = "—"

    # DICOM file locations — tried in order, first existing dir wins
    dicom_search_paths: list[str] = field(default_factory=list)

    # Slice UIDs to display (filenames inside the DICOM dir, no extension)
    slice_uids: list[str] = field(default_factory=list)

    # Findings per slice  uid → {finding, severity}
    # severity: "crit" | "mod" | "mild"
    slice_findings: dict[str, dict] = field(default_factory=dict)

    # Display label per slice  uid → "SL N — description"
    slice_labels: dict[str, str] = field(default_factory=dict)

    # CT window for rendering  (ww, wc)
    window: tuple[float, float] = (400.0, 40.0)

    # Button label shown in the UI
    button_label: str = "Run CTCA digital twin simulation"


# ---------------------------------------------------------------------------
# Per-user registry
# Edit this section to add / modify user profiles.
# ---------------------------------------------------------------------------

#  ── ZHANG, ZHIMING — user: aiq00479@gmail.com ────────────────────────────
_ZHANG_SLICES = ["77172526", "77172537", "77172548", "77172559", "77172570"]

ZHANG_PROFILE = ImagingProfile(
    patient_name  = "ZHANG, ZHIMING",
    patient_id    = "350063",
    patient_dob   = "14/03/1955",
    patient_sex   = "M",
    study_desc    = "CHEART2 — Coronary CTA",
    study_date    = "20/04/2026  15:10",
    heart_rate    = "47 bpm",
    scanner       = "NAEOTOM Alpha.Pro (Siemens)",
    facility      = "Medscan Merrylands",
    referring_dr  = "Dr Thanneermalai Renganathan",
    protocol      = "47 bpm · 70% D · 66 ms · ME_70keV",
    window_str    = "W: 400 / C: 40",
    mAs           = "18",
    dicom_search_paths = [
        r"I:\CTCA Heart Scan DVD 20April2026\DICOM\26052505\16080000",
        r"I:/CTCA Heart Scan DVD 20April2026/DICOM/26052505/16080000",
        "/mnt/i/CTCA Heart Scan DVD 20April2026/DICOM/26052505/16080000",
        str(Path(__file__).parent.parent / "data" / "dicom" / "zhang" / "16080000"),
    ],
    slice_uids = _ZHANG_SLICES,
    slice_labels = {
        "77172526": "SL 1 — Aortic root / LMCA origin",
        "77172537": "SL 2 — Proximal LAD",
        "77172548": "SL 3 — Mid LAD / RCA",
        "77172559": "SL 4 — Distal LAD / Cx",
        "77172570": "SL 5 — RCA mid-distal",
    },
    slice_findings = {
        "77172526": {"finding": "Calcified plaque at LMCA ostium",                          "sev": "mod"},
        "77172537": {"finding": "Mixed plaque, proximal LAD — 40-50% stenosis",              "sev": "mod"},
        "77172548": {"finding": "CRITICAL: Non-calcified plaque, mid LAD — 60-70% stenosis", "sev": "crit"},
        "77172559": {"finding": "Mild calcification, Cx marginal branch",                    "sev": "mild"},
        "77172570": {"finding": "Calcified plaque RCA — 30-40% stenosis",                    "sev": "mod"},
    },
    window       = (400.0, 40.0),
    button_label = "🩻 Run N-1 CTCA digital twin simulation (ZHANG, ZHIMING)",
)

# ── Template for a second user — replace with real values ──────────────────
# Uncomment and fill in when a second patient/user is onboarded.
#
# SMITH_PROFILE = ImagingProfile(
#     patient_name  = "SMITH, JOHN",
#     patient_id    = "123456",
#     patient_dob   = "05/11/1962",
#     patient_sex   = "M",
#     study_desc    = "CHEART1 — Coronary CTA",
#     study_date    = "15/03/2026  09:30",
#     heart_rate    = "62 bpm",
#     scanner       = "NAEOTOM Alpha.Pro (Siemens)",
#     facility      = "Medscan Merrylands",
#     referring_dr  = "Dr Jane Wilson",
#     protocol      = "62 bpm · 75% D · 70 ms · ME_70keV",
#     window_str    = "W: 400 / C: 40",
#     mAs           = "20",
#     dicom_search_paths = [
#         r"D:\PatientScans\SMITH_John\DICOM",
#         str(Path(__file__).parent.parent / "data" / "dicom" / "smith"),
#     ],
#     slice_uids = ["88001100", "88001111", "88001122"],
#     slice_labels = {
#         "88001100": "SL 1 — Aortic root",
#         "88001111": "SL 2 — Proximal LAD",
#         "88001122": "SL 3 — Mid RCA",
#     },
#     slice_findings = {
#         "88001100": {"finding": "No significant plaque",              "sev": "mild"},
#         "88001111": {"finding": "Mild calcification, proximal LAD",   "sev": "mild"},
#         "88001122": {"finding": "Moderate stenosis RCA — 45-55%",     "sev": "mod"},
#     },
#     window       = (400.0, 40.0),
#     button_label = "🩻 Run CTCA simulation (SMITH, JOHN)",
# )

# ---------------------------------------------------------------------------
# Username → profile mapping
# Key   = username exactly as stored in auth DB (email or display name)
# Value = ImagingProfile instance
# ---------------------------------------------------------------------------
USER_IMAGING_PROFILES: dict[str, ImagingProfile] = {
    # Zhi's account
    "aiq00479@gmail.com": ZHANG_PROFILE,
    "Quantum AI":          ZHANG_PROFILE,   # display-name fallback

    # Add more users here:
    # "john.smith@example.com": SMITH_PROFILE,
}

# Fallback shown when no profile matches the logged-in user
NO_PROFILE_SENTINEL = None


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_profile_for_user(username: str | None) -> ImagingProfile | None:
    """
    Return the ImagingProfile for the given username, or None if not found.
    Tries exact match first, then case-insensitive.
    """
    if not username:
        return None
    profile = USER_IMAGING_PROFILES.get(username)
    if profile:
        return profile
    # Case-insensitive fallback
    low = username.lower()
    for key, p in USER_IMAGING_PROFILES.items():
        if key.lower() == low:
            return p
    return None


def get_current_user_profile() -> ImagingProfile | None:
    """
    Convenience: read username from Streamlit session state and return profile.
    Returns None if user has no imaging profile registered.
    """
    import streamlit as st
    username = (
        st.session_state.get("username")
        or st.session_state.get("user_email")
        or st.session_state.get("auth_user")
    )
    return get_profile_for_user(username)
