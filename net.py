"""
net.py - shared HTTP session with retry logic and low-level GET/POST helpers.
"""

from __future__ import annotations

import time

import requests
import requests.adapters

# ---------------------------------------------------------------------------
# Session with automatic retries
# ---------------------------------------------------------------------------


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = requests.adapters.Retry(
        total=8,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _make_session()

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _get(url: str, headers: dict, retries: int = 8) -> dict:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, headers=headers, timeout=25)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                continue
            r.raise_for_status()
            return r.json()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"Connection failed: {exc}") from exc
            time.sleep(2 ** min(attempt, 5))
    raise RuntimeError(f"GET failed after {retries} retries: {url}")


def _post(
    url: str, headers: dict, payload: dict | None = None, retries: int = 8
) -> dict:
    for attempt in range(retries):
        try:
            r = SESSION.post(url, headers=headers, json=payload, timeout=25)
            if r.status_code == 429:
                time.sleep(float(r.json().get("retry_after", 2)) + 0.3)
                continue
            if r.status_code in (200, 201, 204):
                try:
                    return r.json()
                except Exception:
                    return {}
            r.raise_for_status()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"Connection failed: {exc}") from exc
            time.sleep(2 ** min(attempt, 5))
    raise RuntimeError(f"POST failed after {retries} retries: {url}")


def _raise_for_status_verbose(r: requests.Response) -> None:
    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = r.text[:300]
        raise RuntimeError(f"HTTP {r.status_code}: {body}")
