"""Phase 3: a recursive-descent parser from tokens to a Schema.

One method per grammar rule (see ROADMAP.md, Phase 3). Each method reads the
tokens for its rule and returns a piece of the model.
"""

from schemadiagram.model import Column, Schema, Table
from schemadiagram.tokenizer import Token, TokenType, tokenize


class ParseError(Exception):
    def __init__(self, message: str, token: Token):
        super().__init__(f"{message} at line {token.line}, col {token.column}")
        self.token = token


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # --- helpers ---------------------------------------------------------

    def peek(self) -> Token:
        """The current token, without consuming it."""
        return self.tokens[self.pos]

    def advance(self) -> Token:
        """Consume the current token and return it."""
        token = self.tokens[self.pos]
        if token.type is not TokenType.EOF:
            self.pos += 1
        return token

    def match(self, type_: TokenType, value: str | None = None) -> bool:
        """If the current token matches, consume it and return True."""
        # TODO: compare type, and value case-insensitively if given
        raise NotImplementedError

    def expect(self, type_: TokenType, value: str | None = None) -> Token:
        """Consume a token that must match, or raise ParseError."""
        # TODO
        raise NotImplementedError

    # --- grammar rules ---------------------------------------------------

    def parse_schema(self) -> Schema:
        """schema := statement* EOF"""
        # TODO: loop until EOF. Parse CREATE TABLE; skip anything else up to ';'.
        raise NotImplementedError

    def parse_create_table(self) -> Table:
        """create_table := CREATE TABLE [IF NOT EXISTS] name "(" table_item ("," table_item)* ")" """
        raise NotImplementedError

    def parse_column(self) -> Column:
        """column_def := name type column_constraint*"""
        raise NotImplementedError


def parse(text: str) -> Schema:
    """Convenience entry point: SQL text in, Schema out."""
    return Parser(tokenize(text)).parse_schema()
