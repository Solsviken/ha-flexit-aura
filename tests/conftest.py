"""Expose the integration's hardware-facing modules without importing Home Assistant.

``custom_components/flexit_aura/__init__.py`` pulls in Home Assistant, which is
not installed for these tests. Registering a bare package that points at the
same directory lets ``protocol.py`` and ``client.py`` be imported on their own,
relative imports included.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "flexit_aura"

if "flexit_aura" not in sys.modules:
    package = types.ModuleType("flexit_aura")
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["flexit_aura"] = package
