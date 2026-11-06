"""Phase 2: turn raw SQL text into a flat list of tokens.

Example:
    tokenize("CREATE TABLE users (id INT);")
    -> [KEYWORD 'CREATE', KEYWORD 'TABLE', IDENTIFIER 'users', SYMBOL '(',
        IDENTIFIER 'id', IDENTIFIER 'INT', SYMBOL ')', SYMBOL ';', EOF]
"""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    SYMBOL = auto()    # ( ) , ; .
    OPERATOR = auto()  # > < = >= <= <> !=
    EOF = auto()


# Words the parser cares about. Everything else that looks like a word is an IDENTIFIER.
KEYWORDS = {
    "CREATE", "TABLE", "IF", "NOT", "EXISTS", "PRIMARY", "KEY", "FOREIGN",
    "REFERENCES", "UNIQUE", "NULL", "DEFAULT", "CHECK", "CONSTRAINT",
    "ON", "DELETE", "UPDATE", "CASCADE", "SET", "RESTRICT", "NO", "ACTION",
    "ALTER", "ADD",
}

# Single-character punctuation, each its own SYMBOL token.
SYMBOLS = {"(", ")", ",", ";", "."}


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int


class TokenizeError(Exception):
    pass


def tokenize(text: str) -> list[Token]:
    """Split SQL text into tokens. Always ends with an EOF token.

    TODO (Phase 2), roughly in this order:
      - skip whitespace, tracking line and column
      - words: KEYWORD if upper() is in KEYWORDS, else IDENTIFIER
      - symbols ( ) , ; .
      - numbers, string literals 'it''s'
      - comments: -- to end of line, /* ... */
      - operators, including two-character ones like >=
      - quoted identifiers: "x", `x`, [x]
      - raise TokenizeError with line/column for anything unexpected
    """
    tokens: list[Token] = []
    pos = 0      # index of the current character in text
    line = 1     # 1-based, for error messages
    column = 1

    while pos < len(text):
        ch = text[pos]

        if ch == "\n":
            pos += 1
            line += 1
            column = 1
        elif ch.isspace():
            pos += 1
            column += 1
        elif ch.isalpha() or ch == "_":
            start = pos              # where the word begins in text
            start_column = column    # the token's column is where it STARTS

            while pos < len(text) and (text[pos].isalnum() or text[pos] == "_"):
                pos += 1
                column += 1

            word = text[start:pos]

            if word.upper() in KEYWORDS:
                tokens.append(Token(TokenType.KEYWORD, word.upper(), line, start_column))
            else:
                tokens.append(Token(TokenType.IDENTIFIER, word, line, start_column))
        elif ch in SYMBOLS:
            tokens.append(Token(TokenType.SYMBOL, ch, line, column))
            pos += 1
            column += 1
        elif ch == "-" and pos + 1 < len(text) and text[pos + 1] == "-":
            # Line comment: skip to the end of the line, but leave the "\n"
            # for the newline branch so the line count stays right.
            while pos < len(text) and text[pos] != "\n":
                pos += 1
                column += 1
        else:
            raise TokenizeError(f"Unexpected {ch!r} at line {line}, col {column}")

    tokens.append(Token(TokenType.EOF, "", line, column))
    return tokens
