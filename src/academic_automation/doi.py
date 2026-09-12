"""Normalize resolver URLs without truncating legitimate DOI punctuation."""
import re
from urllib.parse import unquote, urlsplit


def normalize(value):
    value = (value or '').strip()
    if re.match(r'^https?://(?:dx\.)?doi\.org/', value, re.I):
        value = unquote(urlsplit(value).path.lstrip('/'))
    # Strip only recognizable tracking suffixes on bare values, not every '?'.
    return re.sub(r'[?&#]utm_[^=]+=[\s\S]*$', '', value, flags=re.I)
