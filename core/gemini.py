"""
core/gemini.py
THE ONLY file that may call the Gemini API.
All agents import gemini_chat() from here — never call Gemini directly.
AGENTS.md Section 5 — The Gemini Call Contract.
"""

import os
import time
import requests
import streamlit as st
from core.config import (
    GEMINI_MODELS, GEMINI_BASE_URL, GEMINI_MAX_TOKENS,
    GEMINI_TEMPERATURE, GEMINI_RETRY_ATTEMPTS, GEMINI_RETRY_CODES,
    HEALTH_SYSTEM_PROMPT,
)


def _get_api_key() -> str | None:
    """Retrieve Gemini API key from environment or Streamlit secrets."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
        except Exception:
            pass
    return key


def _add_log(msg: str) -> None:
    """Safe log helper — works even if session state not fully initialised."""
    try:
        from core.session import add_log
        add_log(msg)
    except Exception:
        pass


def gemini_chat(
    prompt: str,
    system_prompt: str = HEALTH_SYSTEM_PROMPT,
    offline_fallback: str = "_No offline response available for this query._",
) -> str:
    """
    Call Gemini API with automatic 3-model fallback chain.

    Args:
        prompt:           The user's message / query.
        system_prompt:    System instruction (defaults to shared health prompt).
        offline_fallback: String to return if ALL models fail.

    Returns:
        str — always returns a string, never raises an exception to the UI.
    """
    api_key = _get_api_key()

    if not api_key:
        _add_log("GEMINI_NO_KEY")
        return (
            "⚠️ **[SYSTEM]** `GEMINI_API_KEY` not found.\n\n"
            "Add it to your `.env` file locally or as a Space secret on HuggingFace.\n\n"
            f"**Offline fallback:**\n\n{offline_fallback}"
        )

    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents":           [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": GEMINI_MAX_TOKENS,
            "temperature":     GEMINI_TEMPERATURE,
        },
    }

    for model_id, model_label in GEMINI_MODELS:
        url = f"{GEMINI_BASE_URL}/{model_id}:generateContent?key={api_key}"
        _add_log(f"GEMINI→{model_label}")
        delay = 2.0

        for attempt in range(1, GEMINI_RETRY_ATTEMPTS + 1):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=30)

                if r.status_code == 200:
                    data = r.json()
                    text = (
                        data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                            .strip()
                    )
                    if text:
                        _add_log(f"GEMINI_OK:{model_label}")
                        # Store which model responded for sidebar display
                        try:
                            st.session_state["active_gemini_model"] = model_label
                        except Exception:
                            pass
                        return text
                    else:
                        _add_log(f"GEMINI_EMPTY:{model_label}")
                        break  # empty response → try next model

                elif r.status_code in GEMINI_RETRY_CODES:
                    _add_log(f"GEMINI_{r.status_code}:{model_label} attempt {attempt}")
                    if attempt < GEMINI_RETRY_ATTEMPTS:
                        time.sleep(delay)
                        delay *= 2.0
                        continue
                    break  # exhausted retries → try next model

                elif r.status_code == 403:
                    _add_log("GEMINI_403_INVALID_KEY")
                    return (
                        "⚠️ **[SYSTEM]** Gemini API key is invalid or lacks permissions.\n\n"
                        "Check your `GEMINI_API_KEY` in `.env` or HF Space secrets."
                    )

                elif r.status_code == 400:
                    _add_log(f"GEMINI_400:{model_label}")
                    break  # model-specific error → try next model

                else:
                    _add_log(f"GEMINI_ERR_{r.status_code}:{model_label}")
                    break

            except requests.exceptions.Timeout:
                _add_log(f"GEMINI_TIMEOUT:{model_label} attempt {attempt}")
                if attempt < GEMINI_RETRY_ATTEMPTS:
                    time.sleep(delay)
                    delay *= 2.0
                    continue
                break

            except Exception as exc:
                _add_log(f"GEMINI_EXC:{str(exc)[:30]}")
                break

    # All models exhausted
    _add_log("GEMINI_ALL_FAILED→offline")
    return (
        "⚠️ **[SYSTEM]** All Gemini models are currently unavailable (rate limited or 503).\n\n"
        f"**Offline fallback:**\n\n{offline_fallback}"
    )


def get_active_model_label() -> str:
    """Return whichever Gemini model responded last, for sidebar display."""
    try:
        return st.session_state.get("active_gemini_model", GEMINI_MODELS[0][1])
    except Exception:
        return GEMINI_MODELS[0][1]
