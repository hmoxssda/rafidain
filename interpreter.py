"""Interpreter for the Arabi Code language."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Optional

from parser import ArabicParser


class ArabicInterpreter:
    """Execute Arabi Code programs by translating them to Python ASTs."""

    def __init__(self, parser: Optional[ArabicParser] = None) -> None:
        self.parser = parser or ArabicParser()

    def execute(self, source: str, *, scope: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """Execute *source* and return the resulting scope dictionary."""

        python_source = self.parser.translate_to_python(source)
        tree = ast.parse(python_source, filename="<arabi_code>", mode="exec")
        code = compile(tree, filename="<arabi_code>", mode="exec")

        environment = scope if scope is not None else {}
        if "__builtins__" not in environment:
            environment["__builtins__"] = __builtins__

        exec(code, environment)
        return environment

    def run_file(self, path: str | Path, *, scope: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """Execute the Arabi Code file located at *path*."""

        source = Path(path).read_text(encoding="utf-8")
        return self.execute(source, scope=scope)


__all__ = ["ArabicInterpreter"]

