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


def test_identifier_keeps_its_case():
    assert types_and_values("Users") == [(TokenType.IDENTIFIER, "Users"), (TokenType.EOF, "")]


def test_keyword_value_is_uppercased():
    assert tokenize("create")[0].value == "CREATE"


def test_identifier_with_underscore_and_digits():
    assert tokenize("project_id2")[0].value == "project_id2"


def test_word_at_end_of_input():
    # catches a missing pos < len(text) check
    assert len(tokenize("users")) == 2


def test_each_symbol_is_its_own_token():
    assert types_and_values("(),;.") == [
        (TokenType.SYMBOL, "("),
        (TokenType.SYMBOL, ")"),
        (TokenType.SYMBOL, ","),
        (TokenType.SYMBOL, ";"),
        (TokenType.SYMBOL, "."),
        (TokenType.EOF, ""),
    ]


def test_symbol_ends_a_word():
    assert types_and_values("users(") == [
        (TokenType.IDENTIFIER, "users"),
        (TokenType.SYMBOL, "("),
        (TokenType.EOF, ""),
    ]


def test_schema_qualified_name():
    assert types_and_values("public.users") == [
        (TokenType.IDENTIFIER, "public"),
        (TokenType.SYMBOL, "."),
        (TokenType.IDENTIFIER, "users"),
        (TokenType.EOF, ""),
    ]


def test_symbol_column_positions():
    tokens = tokenize("(a, b)")
    assert [t.column for t in tokens[:-1]] == [1, 2, 3, 5, 6]


def test_comment_after_code_on_same_line():
    assert types_and_values("users -- the users table") == [
        (TokenType.IDENTIFIER, "users"),
        (TokenType.EOF, ""),
    ]


def test_comment_at_end_of_input_without_newline():
    # catches a missing pos < len(text) check in the comment loop
    assert types_and_values("-- just a comment") == [(TokenType.EOF, "")]


def test_comment_keeps_line_numbers_right():
    tokens = tokenize("-- one\n-- two\nusers")
    assert (tokens[0].value, tokens[0].line, tokens[0].column) == ("users", 3, 1)


def test_single_dash_is_not_a_comment():
    with pytest.raises(TokenizeError):
        tokenize("- not a comment")