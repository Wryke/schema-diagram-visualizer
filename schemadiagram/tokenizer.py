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
    raise NotImplementedError
