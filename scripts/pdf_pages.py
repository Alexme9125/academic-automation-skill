#!/usr/bin/env python3
"""Compatibility entry point for academic_automation.pdf_pages."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from academic_automation import pdf_pages as _implementation
if __name__ == '__main__':
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
