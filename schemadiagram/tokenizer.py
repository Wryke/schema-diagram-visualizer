"""Phase 2: turn raw SQL text into a flat list of tokens.

Example:
    tokenize("CREATE TABLE users (id INT);")
    -> [KEYWORD 'CREATE', KEYWORD 'TABLE', IDENTIFIER 'users', SYMBOL '(',
        IDENTIFIER 'id', IDENTIFIER 'INT', SYMBOL ')', SYMBOL ';', EOF]

Phase 6: real files hold plenty that isn't a table, like functions and dump
settings. So a character the tokenizer doesn't know becomes an OTHER token
instead of an error, and the parser only objects if it finds one inside a table.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto


class TokenType(Enum):
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    STRING = auto()
    SYMBOL = auto()    # ( ) , ; . and [ ] around array types
    OPERATOR = auto()  # > < = >= <= <> != + - * / :: || and so on
    OTHER = auto()     # any other single character, like @ or $
    EOF = auto()


# Words the parser cares about. Everything else that looks like a word is an IDENTIFIER.
KEYWORDS = {
    "CREATE", "TABLE", "IF", "NOT", "EXISTS", "PRIMARY", "KEY", "FOREIGN",
    "REFERENCES", "UNIQUE", "NULL", "DEFAULT", "CHECK", "CONSTRAINT",
    "ON", "DELETE", "UPDATE", "CASCADE", "SET", "RESTRICT", "NO", "ACTION",
    "ALTER", "ADD",
}

# Single-character punctuation, each its own SYMBOL token. "[" is handled separately,
# because it can also open a quoted name.
SYMBOLS = {"(", ")", ",", ";", ".", "]"}

# Operators. The two-character ones must be checked first, or ">=" would read as ">" then "=".
TWO_CHAR_OPERATORS = {">=", "<=", "<>", "!=", "::", "||", ":="}
ONE_CHAR_OPERATORS = {">", "<", "=", "+", "-", "*", "/", "%", "~", "&", "|", "^"}

# Opening quote of a quoted identifier -> its closing quote.
IDENTIFIER_QUOTES = {'"': '"', "`": "`", "[": "]"}

# The opening of a Postgres dollar-quoted string: $$ or $tag$
DOLLAR_QUOTE = re.compile(r"\$(?:[^\W\d]\w*)?\$")

# The optional exponent of a number: e5, E-3
EXPONENT = re.compile(r"[eE][+-]?\d+")

# The opening of a MySQL or MariaDB versioned comment: /*!50705 or /*M!100100
VERSIONED_COMMENT = re.compile(r"/\*M?!\d*")


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    # The source spelling. A keyword's value is uppercased and a quoted name's value loses
    # its quotes, but the parser needs to see "key" as written, and [index] as quoted.
    raw: str = field(default="", compare=False)


class TokenizeError(Exception):
    pass


def position_after(span: str, line: int, column: int) -> tuple[int, int]:
    """The line and column just after some text that started at the given line and column."""
    newlines = span.count("\n")
    if newlines:
        return line + newlines, len(span) - span.rfind("\n")
    return line, column + len(span)


def read_quoted(
    text: str, pos: int, line: int, column: int, closing: str, backslash_escapes: bool = False,
) -> tuple[str, int, int, int]:
    """Read quoted text whose opening quote is at text[pos].

    Returns the text between the quotes, then the pos, line, and column just
    after the closing quote. A doubled closing quote stands for one literal
    quote, as in 'it''s'. With backslash_escapes, so does a backslash before
    one, as in MySQL's 'it\\'s'. Newlines are allowed inside the quotes.
    """
    start_line, start_column = line, column
    pos += 1
    column += 1
    chars: list[str] = []

    while pos < len(text):
        ch = text[pos]

        if backslash_escapes and ch == "\\" and text[pos + 1:pos + 2] in {closing, "\\"}:
            chars.append(text[pos + 1])
            pos += 2
            column += 2
        elif ch == closing:
            if pos + 1 < len(text) and text[pos + 1] == closing:
                chars.append(closing)
                pos += 2
                column += 2
            else:
                return "".join(chars), pos + 1, line, column + 1
        elif ch == "\n":
            chars.append(ch)
            pos += 1
            line += 1
            column = 1
        else:
            chars.append(ch)
            pos += 1
            column += 1

    raise TokenizeError(f"Unterminated quote starting at line {start_line}, col {start_column}")


def is_alone_on_line(text: str, start: int, end: int) -> bool:
    """True if nothing but whitespace surrounds text[start:end] on its line."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    return not text[line_start:start].strip() and not text[end:line_end if line_end != -1 else len(text)].strip()


def opens_array_brackets(text: str, pos: int, tokens: list[Token]) -> bool:
    """True if the "[" at text[pos] follows a type, as in TEXT[] or INT[3][3].

    Written right after a word it's an array. After a space or a "." it's a
    SQL Server quoted name, as in [id] [int] or dbo.[Order].
    """
    if pos == 0 or not tokens:
        return False
    previous_char = text[pos - 1]
    if previous_char.isalnum() or previous_char in {"_", '"'}:
        return tokens[-1].type in {TokenType.KEYWORD, TokenType.IDENTIFIER}
    return previous_char == "]" and tokens[-1].type is TokenType.SYMBOL


def tokenize(text: str) -> list[Token]:
    """Split SQL text into tokens. Always ends with an EOF token.

    Whitespace and comments produce no tokens. Keywords are uppercased; strings
    and quoted identifiers lose their quotes, and a quoted name is never a keyword.
    SQL Server's GO, alone on a line, becomes the ";" it stands for, and the rows
    after a pg_dump COPY ... FROM stdin are skipped. MySQL runs the code in a versioned
    comment like /*!50705 location GEOMETRY */, so only its markers are removed. Raises
    TokenizeError with the line and column of a quote or comment that never ends.
    """
    tokens: list[Token] = []
    pos = 0      # index of the current character in text
    line = 1     # 1-based, for error messages
    column = 1
    in_versioned_comment = False

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

            while pos < len(text) and (text[pos].isalnum() or text[pos] in {"_", "$"}):
                pos += 1
                column += 1

            word = text[start:pos]

            if word.upper() == "GO" and is_alone_on_line(text, start, pos):
                tokens.append(Token(TokenType.SYMBOL, ";", line, start_column, word))
            elif word.upper() in KEYWORDS:
                tokens.append(Token(TokenType.KEYWORD, word.upper(), line, start_column, word))
            else:
                tokens.append(Token(TokenType.IDENTIFIER, word, line, start_column, word))

            # COPY t FROM stdin; is followed by raw rows, ending at a line holding \.
            end_of_rows = text.find("\n\\.", pos) if word.upper() == "STDIN" else -1
            if end_of_rows != -1:
                tokens.append(Token(TokenType.SYMBOL, ";", line, column, ";"))
                line, column = position_after(text[pos:end_of_rows + 3], line, column)
                pos = end_of_rows + 3
        elif ch.isdigit():
            start = pos
            start_column = column

            while pos < len(text) and text[pos].isdigit():
                pos += 1
                column += 1

            # A "." only belongs to the number if a digit follows it.
            if pos + 1 < len(text) and text[pos] == "." and text[pos + 1].isdigit():
                pos += 1
                column += 1
                while pos < len(text) and text[pos].isdigit():
                    pos += 1
                    column += 1

            exponent = EXPONENT.match(text, pos)
            if exponent:
                pos = exponent.end()
                column += len(exponent.group())

            tokens.append(Token(TokenType.NUMBER, text[start:pos], line, start_column, text[start:pos]))
        elif ch == "'":
            start, start_line, start_column = pos, line, column
            value, pos, line, column = read_quoted(text, pos, line, column, "'", backslash_escapes=True)
            tokens.append(Token(TokenType.STRING, value, start_line, start_column, text[start:pos]))
        elif ch == "[" and opens_array_brackets(text, pos, tokens):
            tokens.append(Token(TokenType.SYMBOL, ch, line, column, ch))
            pos += 1
            column += 1
        elif ch in IDENTIFIER_QUOTES:
            start, start_line, start_column = pos, line, column
            value, pos, line, column = read_quoted(text, pos, line, column, IDENTIFIER_QUOTES[ch])
            tokens.append(Token(TokenType.IDENTIFIER, value, start_line, start_column, text[start:pos]))
        elif ch in SYMBOLS:
            tokens.append(Token(TokenType.SYMBOL, ch, line, column, ch))
            pos += 1
            column += 1
        elif ch == "#" or (ch == "-" and pos + 1 < len(text) and text[pos + 1] == "-"):
            # Line comment: skip to the end of the line, but leave the "\n"
            # for the newline branch so the line count stays right.
            while pos < len(text) and text[pos] != "\n":
                pos += 1
                column += 1
        elif versioned := VERSIONED_COMMENT.match(text, pos):
            column += len(versioned.group())
            pos = versioned.end()
            in_versioned_comment = True
        elif in_versioned_comment and text.startswith("*/", pos):
            pos += 2
            column += 2
            in_versioned_comment = False
        elif ch == "/" and pos + 1 < len(text) and text[pos + 1] == "*":
            # Block comment: may span lines, so newlines still have to be counted.
            start_line, start_column = line, column
            pos += 2
            column += 2

            while pos < len(text) and not text.startswith("*/", pos):
                if text[pos] == "\n":
                    pos += 1
                    line += 1
                    column = 1
                else:
                    pos += 1
                    column += 1

            if pos >= len(text):
                raise TokenizeError(f"Unterminated comment starting at line {start_line}, col {start_column}")

            pos += 2
            column += 2
        elif ch == "$" and (opening := DOLLAR_QUOTE.match(text, pos)) and text.find(opening.group(), opening.end()) != -1:
            # A dollar-quoted string, usually a whole function body, which can hold any character.
            tag = opening.group()
            end = text.find(tag, opening.end())
            value = text[opening.end():end]
            start_line, start_column = line, column
            line, column = position_after(text[pos:end + len(tag)], line, column)
            tokens.append(Token(TokenType.STRING, value, start_line, start_column, text[pos:end + len(tag)]))
            pos = end + len(tag)
        elif text[pos:pos + 2] in TWO_CHAR_OPERATORS:
            tokens.append(Token(TokenType.OPERATOR, text[pos:pos + 2], line, column, text[pos:pos + 2]))
            pos += 2
            column += 2
        elif ch in ONE_CHAR_OPERATORS:
            tokens.append(Token(TokenType.OPERATOR, ch, line, column, ch))
            pos += 1
            column += 1
        else:
            tokens.append(Token(TokenType.OTHER, ch, line, column, ch))
            pos += 1
            column += 1

    tokens.append(Token(TokenType.EOF, "", line, column))
    return tokens
