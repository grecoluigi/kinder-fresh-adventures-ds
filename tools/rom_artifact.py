"""Resolve the playable ROM; legacy names are accepted only for old test artifacts."""
from pathlib import Path

ROM_NAME = "Kinder Fresh Adventures.nds"

def rom_path(directory):
    directory = Path(directory)
    for name in (ROM_NAME, "kinder_fresh.nds"):
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(directory / ROM_NAME)
