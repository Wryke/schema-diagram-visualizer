"""Phase 2 and 6 tests: SQL text in, tokens out."""

from pathlib import Path

import pytest

from schemadiagram.tokenizer import TokenizeError, TokenType, tokenize


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


def test_unknown_character_is_an_other_token():
    assert types_and_values("@") == [(TokenType.OTHER, "@"), (TokenType.EOF, "")]


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
    assert tokenize("- x")[0].type is TokenType.OPERATOR


def test_other_token_records_its_position():
    token = tokenize("a\n  @")[1]
    assert (token.type, token.line, token.column) == (TokenType.OTHER, 2, 3)


# --- numbers ---


@pytest.mark.parametrize("text", ["0", "10", "255", "3.14", "10.50"])
def test_numbers(text):
    assert types_and_values(text) == [(TokenType.NUMBER, text), (TokenType.EOF, "")]


def test_number_inside_type():
    assert types_and_values("VARCHAR(255)") == [
        (TokenType.IDENTIFIER, "VARCHAR"),
        (TokenType.SYMBOL, "("),
        (TokenType.NUMBER, "255"),
        (TokenType.SYMBOL, ")"),
        (TokenType.EOF, ""),
    ]


def test_dot_without_following_digit_is_a_symbol():
    assert types_and_values("10.") == [
        (TokenType.NUMBER, "10"),
        (TokenType.SYMBOL, "."),
        (TokenType.EOF, ""),
    ]


def test_number_has_only_one_decimal_point():
    assert types_and_values("1.2.3") == [
        (TokenType.NUMBER, "1.2"),
        (TokenType.SYMBOL, "."),
        (TokenType.NUMBER, "3"),
        (TokenType.EOF, ""),
    ]


def test_digits_inside_a_word_stay_in_the_word():
    assert types_and_values("line2") == [(TokenType.IDENTIFIER, "line2"), (TokenType.EOF, "")]


def test_number_column_is_where_it_starts():
    tokens = tokenize("  42 x")
    assert (tokens[0].column, tokens[1].column) == (3, 6)


# --- string literals ---


def test_string_loses_its_quotes():
    assert types_and_values("'member'") == [(TokenType.STRING, "member"), (TokenType.EOF, "")]


def test_doubled_quote_is_one_quote():
    assert tokenize("'it''s'")[0].value == "it's"


@pytest.mark.parametrize(("text", "value"), [("''", ""), ("''''", "'")])
def test_empty_string_and_lone_quote(text, value):
    assert types_and_values(text) == [(TokenType.STRING, value), (TokenType.EOF, "")]


def test_keyword_inside_string_is_not_a_keyword():
    assert types_and_values("'CREATE -- /* x'") == [(TokenType.STRING, "CREATE -- /* x"), (TokenType.EOF, "")]


def test_multiline_string_keeps_positions_right():
    tokens = tokenize("'a\nb' c")
    assert (tokens[0].value, tokens[0].line, tokens[0].column) == ("a\nb", 1, 1)
    assert (tokens[1].value, tokens[1].line, tokens[1].column) == ("c", 2, 4)


def test_position_after_doubled_quote_is_right():
    tokens = tokenize("'it''s' x")
    assert tokens[1].column == 9


def test_unterminated_string_reports_where_it_started():
    with pytest.raises(TokenizeError, match="Unterminated quote starting at line 2, col 3"):
        tokenize("a\n  'oops\nb")


# --- block comments ---


def test_block_comment_is_skipped():
    assert types_and_values("a /* hello */ b") == [
        (TokenType.IDENTIFIER, "a"),
        (TokenType.IDENTIFIER, "b"),
        (TokenType.EOF, ""),
    ]


def test_multiline_block_comment_keeps_positions_right():
    tokens = tokenize("/* one\ntwo */ x")
    assert (tokens[0].value, tokens[0].line, tokens[0].column) == ("x", 2, 8)


def test_block_comment_can_hold_stars_and_quotes():
    assert types_and_values("/* ** it's * */") == [(TokenType.EOF, "")]


def test_comment_opener_does_not_close_itself():
    with pytest.raises(TokenizeError, match="Unterminated comment"):
        tokenize("/*/")


def test_unterminated_block_comment_reports_where_it_started():
    with pytest.raises(TokenizeError, match="Unterminated comment starting at line 2, col 1"):
        tokenize("a\n/* oops")


def test_single_slash_is_not_a_comment():
    assert tokenize("/ x")[0].type is TokenType.OPERATOR


# --- operators ---


@pytest.mark.parametrize("op", [">", "<", "=", ">=", "<=", "<>", "!="])
def test_operators(op):
    assert types_and_values(op) == [(TokenType.OPERATOR, op), (TokenType.EOF, "")]


def test_operator_without_spaces():
    assert types_and_values("salary>=0") == [
        (TokenType.IDENTIFIER, "salary"),
        (TokenType.OPERATOR, ">="),
        (TokenType.NUMBER, "0"),
        (TokenType.EOF, ""),
    ]


def test_lone_exclamation_mark_is_an_other_token():
    assert tokenize("!")[0].type is TokenType.OTHER


# --- quoted identifiers ---


@pytest.mark.parametrize("text", ['"my table"', "`my table`", "[my table]"])
def test_quoted_identifier_styles(text):
    assert types_and_values(text) == [(TokenType.IDENTIFIER, "my table"), (TokenType.EOF, "")]


def test_quoted_keyword_is_an_identifier():
    assert types_and_values('"table"') == [(TokenType.IDENTIFIER, "table"), (TokenType.EOF, "")]


def test_quoted_identifier_keeps_its_case():
    assert tokenize("[Users]")[0].value == "Users"


@pytest.mark.parametrize(
    ("text", "value"),
    [('"a""b"', 'a"b'), ("`a``b`", "a`b"), ("[a]]b]", "a]b")],
)
def test_doubled_closing_quote_in_identifier(text, value):
    assert tokenize(text)[0].value == value


@pytest.mark.parametrize("text", ['"oops', "`oops", "[oops"])
def test_unterminated_quoted_identifier_raises(text):
    with pytest.raises(TokenizeError, match="Unterminated quote"):
        tokenize(text)


# --- a whole file ---


def test_tokenizes_all_of_basic_sql():
    text = (Path(__file__).parent.parent / "examples" / "basic.sql").read_text()
    tokens = tokenize(text)
    pairs = {(t.type, t.value) for t in tokens}

    assert sum(t.value == "CREATE" for t in tokens) == 5  # four tables and one index
    assert (TokenType.NUMBER, "255") in pairs
    assert (TokenType.STRING, "member") in pairs
    assert (TokenType.OPERATOR, ">") in pairs
    assert tokens[-1].type is TokenType.EOF

    # Nothing from the comments survives.
    assert not {"self", "relationship", "composite", "parser"} & {t.value for t in tokens}


# --- dialect syntax ---


@pytest.mark.parametrize("op", ["+", "-", "*", "/", "%", "::", "||"])
def test_arithmetic_and_cast_operators(op):
    assert types_and_values(op) == [(TokenType.OPERATOR, op), (TokenType.EOF, "")]


@pytest.mark.parametrize("text", ["1e5", "1E5", "1.5e-3", "2e+10"])
def test_scientific_notation(text):
    assert types_and_values(text) == [(TokenType.NUMBER, text), (TokenType.EOF, "")]


def test_e_without_digits_is_not_an_exponent():
    assert types_and_values("1em") == [
        (TokenType.NUMBER, "1"),
        (TokenType.IDENTIFIER, "em"),
        (TokenType.EOF, ""),
    ]


def test_hash_starts_a_line_comment():
    assert types_and_values("# don't stop\nusers") == [(TokenType.IDENTIFIER, "users"), (TokenType.EOF, "")]


def test_dollar_inside_a_word():
    assert tokenize("a$b")[0].value == "a$b"


@pytest.mark.parametrize(("text", "value"), [(r"'it\'s'", "it's"), (r"'a\\b'", "a\\b"), (r"'a\nb'", r"a\nb")])
def test_backslash_escapes_in_strings(text, value):
    assert types_and_values(text) == [(TokenType.STRING, value), (TokenType.EOF, "")]


@pytest.mark.parametrize(
    "text",
    ["$$body; it's here$$", "$fn$body $$ inside; it's$fn$"],
)
def test_dollar_quoted_strings(text):
    tokens = tokenize(text + " x")
    assert tokens[0].type is TokenType.STRING
    assert tokens[1].value == "x"


def test_dollar_quote_keeps_positions_right():
    tokens = tokenize("$$a\nb$$ c")
    assert (tokens[1].line, tokens[1].column) == (2, 5)


def test_unclosed_dollar_quote_is_not_an_error():
    assert tokenize("$$ x")[0].type is TokenType.OTHER


def test_dollar_parameter_is_not_a_quote():
    assert types_and_values("$1") == [(TokenType.OTHER, "$"), (TokenType.NUMBER, "1"), (TokenType.EOF, "")]


def test_go_alone_on_a_line_ends_a_statement():
    assert types_and_values("a\nGO\nb") == [
        (TokenType.IDENTIFIER, "a"),
        (TokenType.SYMBOL, ";"),
        (TokenType.IDENTIFIER, "b"),
        (TokenType.EOF, ""),
    ]


def test_go_with_windows_line_endings():
    assert tokenize("a\r\ngo\r\nb")[1].value == ";"


def test_go_beside_other_text_is_a_word():
    assert tokenize("go x")[0].type is TokenType.IDENTIFIER
    assert tokenize("x go")[1].type is TokenType.IDENTIFIER


def test_copy_rows_are_skipped():
    text = "COPY t (a) FROM stdin;\nit's a row\n; more\n\\.\nCREATE"
    tokens = tokenize(text)
    assert [t.value for t in tokens[-3:]] == [";", "CREATE", ""]
    assert (tokens[-2].line, tokens[-2].column) == (5, 1)


def test_stdin_without_rows_is_just_a_word():
    assert tokenize("stdin x")[1].value == "x"


def test_array_brackets_after_a_type():
    assert types_and_values("TEXT[]") == [
        (TokenType.IDENTIFIER, "TEXT"),
        (TokenType.SYMBOL, "["),
        (TokenType.SYMBOL, "]"),
        (TokenType.EOF, ""),
    ]


def test_multi_dimensional_array_brackets():
    assert [t.value for t in tokenize("INT[3][3]")[:-1]] == ["INT", "[", "3", "]", "[", "3", "]"]


@pytest.mark.parametrize("text", ["[id] [int]", "dbo.[Order]", "[dbo].[Order]"])
def test_sql_server_brackets_stay_names(text):
    assert all(t.value not in {"[", "]"} for t in tokenize(text))


def test_raw_keeps_the_source_spelling():
    assert tokenize("key")[0].raw == "key"
    assert tokenize("[key]")[0].raw == "[key]"


# --- MySQL versioned comments ---


@pytest.mark.parametrize("opening", ["/*!", "/*!50705", "/*M!100100", "/*!50705 "])
def test_versioned_comment_contents_are_code(opening):
    assert types_and_values(f"{opening} x */ y") == [
        (TokenType.IDENTIFIER, "x"),
        (TokenType.IDENTIFIER, "y"),
        (TokenType.EOF, ""),
    ]


def test_versioned_comment_markers_keep_positions_right():
    tokens = tokenize("/*!50705 x */ y")
    assert (tokens[0].column, tokens[1].column) == (10, 15)


def test_plain_comment_is_still_a_comment():
    assert types_and_values("/* ! x */ y") == [(TokenType.IDENTIFIER, "y"), (TokenType.EOF, "")]


def test_star_slash_outside_a_versioned_comment_is_two_operators():
    assert [t.value for t in tokenize("*/")[:-1]] == ["*", "/"]


def test_star_inside_a_versioned_comment_is_still_an_operator():
    assert [t.value for t in tokenize("/*!1 a * b */")[:-1]] == ["a", "*", "b"]


def test_comment_inside_a_versioned_comment():
    assert [t.value for t in tokenize("/*!1 a /* b */ c */ d")[:-1]] == ["a", "c", "d"]
