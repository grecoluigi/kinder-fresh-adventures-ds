"""Publish an optimized SDK ROM using its release filename and SHA-256 sidecar."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

def publish(source, destination):
    source, destination = Path(source), Path(destination)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if not destination.exists() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        fd, temporary = tempfile.mkstemp(prefix=".rom-", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copyfile(source, temporary)
            os.chmod(temporary, 0o644)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
    destination.with_suffix(".nds.sha256").write_text(f"{digest}  {destination.name}\n")
    print(f"ROM: {destination} ({destination.stat().st_size:,} bytes; SHA256 {digest})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    publish(args.source, args.destination)
