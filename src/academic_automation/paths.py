"""Paths shared by source checkouts and unpacked skills."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'


def state_dir():
    # Shared across installed copies: two agents must not control the same browser.
    override = os.environ.get('ACADEMIC_STATE_DIR')
    return Path(override).expanduser() if override else Path.home() / '.academic-automation'


def downloads_dir():
    return Path(os.environ.get('CNKI_DOWNLOADS_DIR', str(Path.home() / 'Downloads'))).expanduser()
