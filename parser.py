"""Parser and source translator for the Arabi Code language."""

from __future__ import annotations

import ast
import re
from typing import Dict, List, Optional, Sequence, Tuple

from lexer import ArabicLexer, strip_diacritics


_DEFAULT_IMPORT_MAP: Dict[str, str] = {
    "الرياضيات": "math",
    "عشوائي": "random",
    "نظام": "sys",
    "تاريخ": "datetime",
    "مسارات": "pathlib",
}


class ArabicParser:
    """Convert Arabi Code source into a Python AST."""

    INDENT = "    "

    def __init__(self, *, lexer: Optional[ArabicLexer] = None, import_map: Optional[Dict[str, str]] = None) -> None:
        self.lexer = lexer or ArabicLexer()
        self.import_map = dict(_DEFAULT_IMPORT_MAP)
        if import_map:
            self.import_map.update(import_map)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(self, source: str) -> ast.AST:
        """Parse *source* and return a Python :class:`ast.Module`."""

        # Tokenise first to surface lexical errors early and to respect the
        # lexer requirement of the language pipeline.
        self.lexer.tokenize(source)
        python_source = self.translate_to_python(source)
        return ast.parse(python_source, mode="exec")

    def translate_to_python(self, source: str) -> str:
        """Translate Arabi Code source into valid Python source code."""

        normalised = self._prepare_source(source)
        lines = normalised.splitlines()
        python_lines = self._process_lines(lines)
        return "\n".join(python_lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _prepare_source(self, source: str) -> str:
        clean = strip_diacritics(source)
        replacements = {
            "؛": ";",
            "،": ",",
            "“": '"',
            "”": '"',
            "«": '"',
            "»": '"',
        }
        for old, new in replacements.items():
            clean = clean.replace(old, new)

        clean = clean.replace("{", "{\n").replace("}", "\n}")
        clean = re.sub(r"}\s*وإلا", "}\nوإلا", clean)
        clean = re.sub(r"}\s*وإلا إذا", "}\nوإلا إذا", clean)
        clean = re.sub(r"\n+", "\n", clean)
        return clean

    def _process_lines(self, lines: Sequence[str]) -> List[str]:
        output: List[str] = []
        indent_level = 0
        brace_stack: List[int] = []

        for raw in lines:
            stripped = raw.strip()

            if not stripped:
                output.append("")
                continue

            while stripped.startswith("}"):
                if not brace_stack:
                    raise SyntaxError("Unexpected '}'")
                indent_level -= brace_stack.pop()
                stripped = stripped[1:].strip()
            if not stripped:
                continue

            open_brace = stripped.endswith("{")
            if open_brace:
                stripped = stripped[:-1].strip()

            translated_lines, indent_increase, prelude = self._translate_statement(stripped, indent_level, open_brace)

            for pre_line in prelude:
                output.append(self._indent_line(pre_line, indent_level))

            for line in translated_lines:
                output.append(self._indent_line(line, indent_level))

            if open_brace:
                brace_stack.append(indent_increase)
                indent_level += indent_increase

        if brace_stack:
            raise SyntaxError("Unmatched '{'")

        return output

    def _indent_line(self, line: str, indent_level: int) -> str:
        if not line:
            return ""
        return f"{self.INDENT * indent_level}{line}"

    def _translate_statement(
        self,
        line: str,
        indent_level: int,
        open_brace: bool,
    ) -> Tuple[List[str], int, List[str]]:
        indent_increase = 1 if open_brace else 0
        prelude: List[str] = []

        if line.startswith("متغير "):
            line = line[len("متغير ") :].strip()
            return [self._translate_expression_statement(line)], indent_increase, prelude

        if line.startswith("إذا"):
            condition = self._extract_parenthesised(line[len("إذا") :].strip())
            return [f"if {self._translate_expression(condition)}:"], 1, prelude

        if line.startswith("وإلا إذا"):
            condition = self._extract_parenthesised(line[len("وإلا إذا") :].strip())
            return [f"elif {self._translate_expression(condition)}:"], 1, prelude

        if line.startswith("وإلا"):
            return ["else:"], 1, prelude

        if line.startswith("دالة "):
            match = re.match(r"دالة\s+([\w\u0600-\u06FF_]+)\s*\((.*)\)$", line)
            if not match:
                raise SyntaxError(f"صيغة دالة غير صحيحة: {line}")
            name, args = match.groups()
            args = self._translate_parameters(args)
            return [f"def {name}({args}):"], 1, prelude

        if line.startswith("رجع"):
            expr = line[len("رجع") :].strip()
            if expr:
                return [f"return {self._translate_expression(expr)}"], 0, prelude
            return ["return"], 0, prelude

        if line.startswith("اطبع"):
            expr = line[len("اطبع") :].strip()
            if expr.startswith("(") and expr.endswith(")"):
                expr = expr[1:-1]
            return [f"print({self._translate_expression(expr)})"], indent_increase, prelude

        if line.startswith("استورد "):
            remainder = line[len("استورد ") :].strip()
            module = self.import_map.get(remainder, remainder)
            return [f"import {module}"], indent_increase, prelude

        if line.startswith("كرر"):
            header = line[len("كرر") :].strip()
            if header.startswith("(") and header.endswith(")"):
                inner = header[1:-1].strip()
            else:
                inner = header
            c_style = self._parse_c_style_loop(inner)
            if c_style:
                for_line, prelude_assignment = c_style
                if prelude_assignment:
                    prelude.append(prelude_assignment)
                return [for_line], 1, prelude
            if ";" in inner:
                raise SyntaxError("تعذر تحويل حلقة كرر ذات الصيغة المعطاة")
            condition = self._translate_expression(inner)
            return [f"while {condition}:"], 1, prelude

        if line.startswith("كائن "):
            if not open_brace:
                raise SyntaxError("تعريف الكائن يتطلب كتلة")
            name = line[len("كائن ") :].strip()
            return [f"class {name}:", f"{self.INDENT}def __init__(self):"], 2, prelude

        if line.startswith("بينما"):
            condition = self._extract_parenthesised(line[len("بينما") :].strip())
            return [f"while {self._translate_expression(condition)}:"], 1, prelude

        inc_match = re.match(r"([\w\u0600-\u06FF_]+)\s*\+\+$", line)
        if inc_match:
            var = inc_match.group(1)
            return [f"{var} += 1"], indent_increase, prelude

        dec_match = re.match(r"([\w\u0600-\u06FF_]+)\s*--$", line)
        if dec_match:
            var = dec_match.group(1)
            return [f"{var} -= 1"], indent_increase, prelude

        translated = self._translate_expression(line)
        if open_brace and not translated.rstrip().endswith(":"):
            translated = f"{translated}:"
        return [translated], indent_increase, prelude

    def _translate_expression_statement(self, statement: str) -> str:
        return self._translate_expression(statement)

    def _translate_parameters(self, params: str) -> str:
        params = params.strip()
        if not params:
            return ""
        pieces = [p.strip() for p in params.split(",") if p.strip()]
        translated = [self._translate_expression(p) for p in pieces]
        return ", ".join(translated)

    def _translate_expression(self, expr: str) -> str:
        expr = expr.strip()
        return self._replace_keywords(expr)

    def _replace_keywords(self, expr: str) -> str:
        replacements: List[Tuple[str, str, bool]] = [
            ("لا شيء", "None", True),
            ("لاشيء", "None", True),
            ("هذا.", "self.", False),
            ("ليس", " not ", True),
            ("صح", "True", True),
            ("خطأ", "False", True),
            ("خطا", "False", True),
            ("أو", " or ", True),
            ("و", " and ", True),
        ]

        result: List[str] = []
        i = 0
        length = len(expr)
        in_string = False
        string_char = ""

        while i < length:
            ch = expr[i]

            if in_string:
                result.append(ch)
                if ch == string_char and not self._is_escaped(expr, i):
                    in_string = False
                i += 1
                continue

            if ch in {'"', "'"}:
                in_string = True
                string_char = ch
                result.append(ch)
                i += 1
                continue

            replaced = False
            for arabic, english, boundary in replacements:
                if expr.startswith(arabic, i):
                    start = i
                    end = i + len(arabic)
                    if boundary and not self._has_word_boundaries(expr, start, end):
                        continue
                    result.append(english)
                    i = end
                    replaced = True
                    break

            if replaced:
                continue

            result.append(ch)
            i += 1

        return "".join(result)

    @staticmethod
    def _is_escaped(text: str, index: int) -> bool:
        backslash_count = 0
        i = index - 1
        while i >= 0 and text[i] == "\\":
            backslash_count += 1
            i -= 1
        return (backslash_count % 2) == 1

    @staticmethod
    def _has_word_boundaries(text: str, start: int, end: int) -> bool:
        def is_identifier_char(ch: str) -> bool:
            return ch.isalnum() or ch == "_"

        before_ok = start == 0 or not is_identifier_char(text[start - 1])
        after_ok = end >= len(text) or not is_identifier_char(text[end])
        return before_ok and after_ok

    def _extract_parenthesised(self, text: str) -> str:
        text = text.strip()
        if text.startswith("(") and text.endswith(")"):
            return text[1:-1].strip()
        return text

    def _parse_c_style_loop(self, inner: str) -> Optional[Tuple[str, Optional[str]]]:
        if ";" not in inner:
            return None

        parts = [part.strip() for part in inner.split(";")]
        if len(parts) != 3:
            return None

        init, condition, update = parts

        if init.startswith("متغير "):
            init = init[len("متغير ") :].strip()

        if "=" not in init:
            return None
        var_name, start_expr = [segment.strip() for segment in init.split("=", 1)]
        start_expr = self._translate_expression(start_expr)

        condition_match = re.match(rf"{re.escape(var_name)}\s*([<>]=?)\s*(.+)", condition)
        if not condition_match:
            return None
        operator, end_expr = condition_match.groups()
        end_expr = self._translate_expression(end_expr.strip())

        step_info = self._parse_update_expression(var_name, update)
        if not step_info:
            return None
        step_value = step_info

        inclusive = operator in {"<=", ">="}
        if inclusive and step_value not in {"1", "-1"}:
            return None

        if step_value.startswith("-"):
            range_end = f"({end_expr} - 1)" if inclusive else end_expr
        else:
            range_end = f"({end_expr} + 1)" if inclusive else end_expr

        if step_value in {"1", "-1"}:
            if step_value == "1":
                for_line = f"for {var_name} in range({start_expr}, {range_end}):"
            else:
                for_line = f"for {var_name} in range({start_expr}, {range_end}, -1):"
        else:
            for_line = f"for {var_name} in range({start_expr}, {range_end}, {step_value}):"

        return for_line, None

    def _parse_update_expression(self, var_name: str, update: str) -> Optional[str]:
        update = update.strip()
        if update == f"{var_name}++":
            return "1"
        if update == f"{var_name}--":
            return "-1"

        add_match = re.match(rf"{re.escape(var_name)}\s*\+=\s*(.+)", update)
        if add_match:
            return self._translate_expression(add_match.group(1).strip())

        sub_match = re.match(rf"{re.escape(var_name)}\s*\-=\s*(.+)", update)
        if sub_match:
            expr = self._translate_expression(sub_match.group(1).strip())
            return f"-({expr})"

        return None


__all__ = ["ArabicParser"]

