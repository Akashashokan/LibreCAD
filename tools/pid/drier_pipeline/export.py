from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def export_pdf_if_available(dxf_path: Path, pdf_path: Path) -> str:
    librecad = shutil.which("librecad")
    if not librecad:
        return "librecad not found; skipped PDF export"

    cmd = [
        librecad,
        "dxf2pdf",
        "--fit",
        "--center",
        "--paper", "A0",
        "--outfile", str(pdf_path),
        str(dxf_path),
    ]
    subprocess.run(cmd, check=True)
    if not pdf_path.exists() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"Generated PDF is blank: {pdf_path}")
    return f"exported {pdf_path}"
