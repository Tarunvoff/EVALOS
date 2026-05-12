from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a string."""

    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)

    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group(1))
