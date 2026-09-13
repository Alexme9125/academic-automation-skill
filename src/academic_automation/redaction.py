"""Keep extension connection credentials out of persisted/output diagnostics."""
import os
import re
from urllib.parse import urlsplit, urlunsplit


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    token = os.environ.get('PLAYWRIGHT_MCP_EXTENSION_TOKEN', '')
    if token:
        value = value.replace(token, '[REDACTED]')
    def internal(match):
        p = urlsplit(match.group())
        return urlunsplit((p.scheme, p.netloc, p.path, '', ''))
    return re.sub(r'chrome-extension://[^\s<>"\'\\]+', internal, value)
