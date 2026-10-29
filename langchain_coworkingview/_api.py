"""Minimal client for the public CoworkingView API. Standard library only."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from langchain_coworkingview import __version__

BASE_URL = "https://api.coworkingview.com"
TIMEOUT_SECONDS = 15
LOCALES = ("en", "de", "es")
WORKSPACE_TYPES = (
    "private_office",
    "fix_desk",
    "flex_desk",
    "day_pass",
    "meeting_room",
    "virtual_office",
    "event_space",
    "membership",
    "exclusive_bereich",
)
_SLUG = re.compile(r"^[a-z0-9-]{1,200}$")
_SPACE_SEGMENT = {"en": "workspace", "de": "buero", "es": "oficina"}
_PER = {"hour": "/hour", "day": "/day", "week": "/week", "month": "/month", "year": "/year"}


class CoworkingViewAPIError(RuntimeError):
    """The API answered with an error, or could not be reached."""


def slug(value: str, what: str) -> str:
    """Normalise and validate a slug, so a bad value fails before any request."""
    cleaned = str(value).strip().lower()
    if not _SLUG.match(cleaned):
        raise ValueError(f'{what} "{value}" is not a slug, e.g. "berlin" or "signature-potsdamer-platz-berlin"')
    return cleaned


def get(path: str, params: dict[str, Any], base_url: str = BASE_URL) -> dict[str, Any]:
    """GET `path` with `params` (None values dropped) and decode the JSON body."""
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    url = f"{base_url.rstrip('/')}{path}" + (f"?{query}" if query else "")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"langchain-coworkingview/{__version__} (+https://coworkingview.com)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            problem = json.loads(error.read().decode("utf-8"))
            detail = problem.get("detail") or problem.get("title") or ""
        except (ValueError, AttributeError):
            pass
        raise CoworkingViewAPIError(f"CoworkingView API {error.code}: {detail}".rstrip(": ")) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise CoworkingViewAPIError(f"Could not reach the CoworkingView API: {error}") from error


def money(value: Any) -> str | None:
    """`{"amount": 290, "currency": "EUR"}` -> `"EUR 290"`."""
    if not isinstance(value, dict) or "amount" not in value:
        return None
    amount = float(value["amount"])
    text = f"{amount:,.0f}" if amount.is_integer() else f"{amount:,.2f}"
    return f"{value.get('currency', '')} {text}".strip()


def space_url(space_slug: str, locale: str) -> str:
    return f"https://coworkingview.com/{locale}/{_SPACE_SEGMENT[locale]}/{urllib.parse.quote(space_slug)}"


def per(period: str | None) -> str:
    return _PER.get(period or "", "")
