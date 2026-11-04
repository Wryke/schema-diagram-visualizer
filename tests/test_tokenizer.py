"""Phase 2 tests. Delete the pytestmark line when you start the tokenizer,
then add more tests as you go (aim for 15+)."""

import pytest

from schemadiagram.tokenizer import TokenizeError, TokenType, tokenize

# pytestmark = pytest.mark.skip(reason="Phase 2: delete this line when you start the tokenizer")


def types_and_values(text):
    return [(t.type, t.value) for t in tokenize(text)]


def test_empty_input_is_just_eof():
    assert types_and_values("") == [(TokenType.EOF, "")]


def test_keywords_are_case_insensitive():
    assert tokenize("create")[0].type is TokenType.KEYWORD


def test_simple_create_table():
    assert types_and_values("CREATE TABLE users (id INT);") == [
        (TokenType.KEYWORD, "CREATE"),
        (TokenType.KEYWORD, "TABLE"),
        (TokenType.IDENTIFIER, "users"),
        (TokenType.SYMBOL, "("),
        (TokenType.IDENTIFIER, "id"),
        (TokenType.IDENTIFIER, "INT"),
        (TokenType.SYMBOL, ")"),
        (TokenType.SYMBOL, ";"),
        (TokenType.EOF, ""),
    ]


def test_line_comments_are_skipped():
    assert types_and_values("-- hello\nusers") == [
        (TokenType.IDENTIFIER, "users"),
        (TokenType.EOF, ""),
    ]


def test_tracks_line_numbers():
    tokens = tokenize("a\n  b")
    assert (tokens[1].line, tokens[1].column) == (2, 3)


def test_unexpected_character_raises():
    with pytest.raises(TokenizeError):
        tokenize("@")


def test_whitespace_only_is_just_eof():
    tokens = tokenize("  \n\t ")
    assert [t.type for t in tokens] == [TokenType.EOF]
    assert tokens[0].line == 2