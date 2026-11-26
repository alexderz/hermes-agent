"""Payload digest of one pinned intercom frame.

The encoding matches the admission ledger's fingerprint for a queued text submit.
This module does not import the ledger.
"""

from __future__ import annotations

import hashlib
import json


def frame_digest(target: str, text: str) -> str:
    """Digest of a queue submit whose payload is exactly ``{"text": text}``."""
    encoded = json.dumps(
        {"target": target, "payload": {"input": {"text": text}, "intent": "queue"}},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(encoded).hexdigest()
