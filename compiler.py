"""Compiler that converts Arabi Code into Python source files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from parser import ArabicParser


class ArabicCompiler:
    """Compile Arabi Code source into equivalent Python code."""

    def __init__(self, parser: Optional[ArabicParser] = None) -> None:
        self.parser = parser or ArabicParser()

    def compile_to_python(self, source: str) -> str:
        """Return Python code generated from *source*."""

        return self.parser.translate_to_python(source)

    def compile_file(self, path: str | Path) -> str:
        """Read *path* and return the translated Python code."""

        source = Path(path).read_text(encoding="utf-8")
        return self.compile_to_python(source)

    def write_python_file(self, source_path: str | Path, target_path: str | Path) -> Path:
        """Compile *source_path* and write the Python output to *target_path*."""

        python_code = self.compile_file(source_path)
        target = Path(target_path)
        target.write_text(python_code, encoding="utf-8")
        return target


__all__ = ["ArabicCompiler"]

