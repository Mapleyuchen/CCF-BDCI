"""Versioned controlled memory evaluation, kept separate from legacy pilots."""

import os
from pathlib import Path

os.environ.setdefault("JIUWENSWARM_DATA_DIR",
                      str(Path(__file__).resolve().parents[1] / "results/.runtime"))

PROTOCOL_VERSION = "memory-eval-v2.0"
