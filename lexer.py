"""Arabic Code Lexer.

This module implements a simple lexer for the "Arabi Code" language.
It is responsible for converting a source string that uses Arabic
keywords into a sequence of tokens that will later be consumed by the
parser.  The lexer strips Arabic diacritics, supports right-to-left
keywords, and recognises both Arabic and Latin identifiers so that
existing Python ecosystem names can be imported without translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# Arabic combining marks (diacritics) that should be ignored by the lexer.
_DIACRITIC_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")


def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritics from *text*.

    The language treats diacritics as optional spelling aids, therefore
    the lexer erases them before tokenisation so that `فَتْحَة` and
    `فتحة` are recognised as the same identifier.
    """

    return _DIACRITIC_RE.sub("", text)


@dataclass(frozen=True)
class Token:
    """A lexical token produced by :class:`ArabicLexer`."""

    type: str
    value: str
    line: int
    column: int


class ArabicLexer:
    """Tokenise Arabic source code.

    The lexer intentionally keeps the token set close to Python's while
    recognising the Arabic keywords that Arabi Code introduces.  The
    :class:`ArabicParser` performs the semantic translation, therefore
    the lexer focuses solely on structural correctness.
    """

    #: Token specification expressed as regular expressions.  The order
    #: matters: the lexer finds the first matching named group.
    _TOKEN_SPECIFICATION: List[tuple[str, str]] = [
        ("NUMBER", r"\d+(?:\.\d+)?"),
        (
            "STRING",
            r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'',
        ),
        ("COMMENT", r"//[^\n]*|#[^\n]*"),
        ("NEWLINE", r"\n"),
        ("SKIP", r"[ \t\r]+"),
        ("OP", r"\+\+|--|==|!=|<=|>=|\+=|-=|\*=|/=|//=|%=|&&|\|\||[+\-*/%<>=!&|^]"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("LBRACE", r"\{"),
        ("RBRACE", r"\}"),
        ("LBRACKET", r"\["),
        ("RBRACKET", r"\]"),
        ("COMMA", r","),
        ("SEMI", r";"),
        ("DOT", r"\."),
        (
            "ID",
            r"[\u0600-\u06FFA-Za-z_][\u0600-\u06FFA-Za-z_0-9]*",
        ),
        ("MISMATCH", r"."),
    ]

    #: Arabic keywords that need to be distinguished from identifiers.
    _KEYWORDS = {
        "متغير",
        "دالة",
        "رجع",
        "إذا",
        "وإلا",
        "كرر",
        "اطبع",
        "كائن",
        "هذا",
        "استورد",
        "صح",
        "خطأ",
        "بينما",
    }

    def __init__(self) -> None:
        parts = [f"(?P<{name}>{pattern})" for name, pattern in self._TOKEN_SPECIFICATION]
        self._token_regex = re.compile("|".join(parts))

    def tokenize(self, code: str) -> List[Token]:
        """Tokenise *code* and return the resulting list of :class:`Token`.

        The lexer strips diacritics before scanning.  Unknown characters
        raise :class:`SyntaxError` with precise line/column information.
        """

        clean_code = strip_diacritics(code)
        tokens: List[Token] = []
        line_num = 1
        line_start = 0

        for match in self._token_regex.finditer(clean_code):
            kind = match.lastgroup
            value = match.group()
            column = match.start() - line_start + 1

            if kind == "NEWLINE":
                line_num += 1
                line_start = match.end()
                continue

            if kind in {"SKIP", "COMMENT"}:
                continue

            if kind == "ID" and value in self._KEYWORDS:
                kind = "KEYWORD"

            if kind == "STRING":
                value = self._unescape_string(value)

            if kind == "MISMATCH":
                raise SyntaxError(f"Unexpected character {value!r} at line {line_num}, column {column}")

            tokens.append(Token(kind, value, line_num, column))

        return tokens

    @staticmethod
    def _unescape_string(token: str) -> str:
        """Interpret escape sequences inside *token* and drop the quotes."""

        if not token:
            return token

        quote = token[0]
        if quote not in {'"', "'"}:
            return token

        inner = token[1:-1]
        return bytes(inner, "utf-8").decode("unicode_escape")


__all__ = ["ArabicLexer", "Token", "strip_diacritics"]

