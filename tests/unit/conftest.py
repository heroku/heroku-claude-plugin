"""Shared fixtures for unit tests."""
import sys
from pathlib import Path

# Ensure scripts/ is importable without installation
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
