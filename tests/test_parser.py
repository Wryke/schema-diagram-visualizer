"""Phase 3 tests: SQL text in, Schema out."""

from pathlib import Path

import pytest

from examples.hand_built import schema as hand_built_schema
from schemadiagram.model import ForeignKey
from schemadiagram.parser import ParseError, parse


def parse_table(body):
    """Parse one table with the given body and return it."""
    return parse(f"CREATE TABLE t ({body});").tables[0]


def parse_column(definition):
    """Parse one table with one column and return the column."""
    return parse_table(definition).columns[0]


def test_single_table_with_columns():
    schema = parse("CREATE TABLE users (id INT, email VARCHAR(255));")
    assert [t.name for t in schema.tables] == ["users"]
    assert [(c.name, c.type) for c in schema.tables[0].columns] == [
        ("id", "INT"),
        ("email", "VARCHAR(255)"),
    ]


def test_inline_self_reference():
    schema = parse("CREATE TABLE employees (id INT PRIMARY KEY, manager_id INT REFERENCES employees(id));")
    fk = schema.tables[0].foreign_keys[0]
    assert (fk.from_table, fk.from_columns, fk.to_table, fk.to_columns) == (
        "employees", ["manager_id"], "employees", ["id"],
    )


def test_unknown_statements_are_skipped():
    schema = parse("CREATE INDEX i ON t(x); CREATE TABLE t (x INT);")
    assert [t.name for t in schema.tables] == ["t"]


def test_parses_basic_sql_into_the_hand_built_schema():
    text = (Path(__file__).parent.parent / "examples" / "basic.sql").read_text()
    assert parse(text) == hand_built_schema


# --- statements ---


def test_empty_input_has_no_tables():
    assert parse("").tables == []


def test_comment_only_input_has_no_tables():
    assert parse("-- nothing\n/* here */").tables == []


def test_multiple_tables_keep_their_order():
    schema = parse("CREATE TABLE b (x INT); CREATE TABLE a (y INT);")
    assert [t.name for t in schema.tables] == ["b", "a"]


def test_last_statement_does_not_need_a_semicolon():
    assert parse("CREATE TABLE t (x INT)").tables[0].name == "t"


def test_stray_semicolons_are_ignored():
    assert [t.name for t in parse(";; CREATE TABLE t (x INT);;").tables] == ["t"]


def test_if_not_exists():
    assert parse("CREATE TABLE IF NOT EXISTS t (x INT);").tables[0].name == "t"


def test_table_options_after_the_body_are_skipped():
    schema = parse("CREATE TABLE a (x INT) ENGINE=InnoDB; CREATE TABLE b (y INT);")
    assert [t.name for t in schema.tables] == ["a", "b"]


def test_keywords_are_case_insensitive():
    table = parse("create table t (x int primary key not null);").tables[0]
    assert table.primary_key == ["x"]
    assert table.columns[0].nullable is False


def test_quoted_names():
    table = parse('CREATE TABLE "order" ("select" INT, [my col] INT);').tables[0]
    assert table.name == "order"
    assert [c.name for c in table.columns] == ["select", "my col"]


# --- types ---


@pytest.mark.parametrize(
    "type_text",
    ["INT", "VARCHAR(255)", "NUMERIC(10, 2)", "DOUBLE PRECISION", "TIMESTAMP WITH TIME ZONE",
     "TIMESTAMP(3) WITH TIME ZONE", "CHARACTER VARYING(50)"],
)
def test_types_are_kept_as_text(type_text):
    assert parse_column(f"x {type_text}").type == type_text


def test_type_spacing_is_normalized():
    assert parse_column("x NUMERIC ( 10,2 )").type == "NUMERIC(10, 2)"


def test_enum_type_keeps_its_strings():
    assert parse_column("x ENUM('a', 'b')").type == "ENUM('a', 'b')"


# --- column constraints ---


def test_column_defaults_when_no_constraints():
    column = parse_column("x INT")
    assert (column.nullable, column.unique, column.default, column.check) == (True, False, None, None)


def test_not_null():
    assert parse_column("x INT NOT NULL").nullable is False


def test_explicit_null():
    assert parse_column("x INT NULL").nullable is True


def test_unique():
    assert parse_column("x INT UNIQUE").unique is True


def test_inline_primary_key_goes_on_the_table():
    assert parse_table("x INT PRIMARY KEY, y INT").primary_key == ["x"]


def test_constraints_in_any_order():
    column = parse_column("x INT DEFAULT 0 UNIQUE CHECK (x > 0) NOT NULL")
    assert (column.default, column.unique, column.check, column.nullable) == ("0", True, "x > 0", False)


def test_named_column_constraint():
    assert parse_column("x INT CONSTRAINT x_required NOT NULL").nullable is False


# --- DEFAULT values ---


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("0", "0"),
        ("1.5", "1.5"),
        ("'member'", "'member'"),
        ("'it''s'", "'it''s'"),
        ("NULL", "NULL"),
        ("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("now()", "now()"),
        ("(1 > 0)", "(1 > 0)"),
    ],
)
def test_default_values(sql, expected):
    assert parse_column(f"x INT DEFAULT {sql}").default == expected


def test_default_null_then_another_constraint():
    column = parse_column("x INT DEFAULT NULL UNIQUE")
    assert (column.default, column.unique) == ("NULL", True)


def test_default_stops_before_not_null():
    column = parse_column("x INT DEFAULT 5 NOT NULL")
    assert (column.default, column.nullable) == ("5", False)


def test_default_stops_at_the_next_column():
    table = parse_table("x INT DEFAULT 5, y INT")
    assert [c.name for c in table.columns] == ["x", "y"]


# --- CHECK ---


def test_column_check_drops_outer_parentheses():
    assert parse_column("x INT CHECK (x > 0)").check == "x > 0"


def test_check_keeps_nested_parentheses():
    assert parse_column("x INT CHECK ((x > 0) AND (x < 10))").check == "(x > 0) AND (x < 10)"


def test_check_keeps_space_before_parenthesis_after_word_operator():
    assert parse_column("x INT CHECK (x IN (1, 2))").check == "x IN (1, 2)"


def test_check_with_function_and_string():
    assert parse_column("x TEXT CHECK (lower(x) <> 'a')").check == "lower(x) <> 'a'"


def test_second_column_check_goes_on_the_table():
    table = parse_table("x INT CHECK (x > 0) CHECK (x < 9)")
    assert table.columns[0].check == "x > 0"
    assert table.checks == ["x < 9"]


def test_table_check():
    assert parse_table("x INT, y INT, CHECK (x < y)").checks == ["x < y"]


# --- foreign keys ---


def test_inline_foreign_key():
    assert parse_table("x INT REFERENCES users(id)").foreign_keys == [
        ForeignKey("t", ["x"], "users", ["id"]),
    ]


def test_table_level_foreign_key():
    assert parse_table("x INT, FOREIGN KEY (x) REFERENCES users(id)").foreign_keys == [
        ForeignKey("t", ["x"], "users", ["id"]),
    ]


def test_composite_foreign_key():
    table = parse_table("a INT, b INT, FOREIGN KEY (a, b) REFERENCES other(c, d)")
    assert table.foreign_keys == [ForeignKey("t", ["a", "b"], "other", ["c", "d"])]


def test_constraint_name_is_kept():
    assert parse_table("x INT, CONSTRAINT fk_x FOREIGN KEY (x) REFERENCES u(id)").foreign_keys[0].name == "fk_x"
    assert parse_table("x INT CONSTRAINT fk_x REFERENCES u(id)").foreign_keys[0].name == "fk_x"


@pytest.mark.parametrize("action", ["CASCADE", "RESTRICT", "SET NULL", "SET DEFAULT", "NO ACTION"])
def test_on_delete_actions(action):
    assert parse_table(f"x INT REFERENCES u(id) ON DELETE {action}").foreign_keys[0].on_delete == action


def test_on_update_is_accepted_in_either_order():
    first = parse_table("x INT REFERENCES u(id) ON UPDATE CASCADE ON DELETE SET NULL").foreign_keys[0]
    second = parse_table("x INT REFERENCES u(id) ON DELETE SET NULL ON UPDATE CASCADE").foreign_keys[0]
    assert first.on_delete == second.on_delete == "SET NULL"


def test_reference_without_columns_means_the_primary_key():
    schema = parse("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES u);")
    assert schema.foreign_keys[0].to_columns == ["id"]


def test_reference_without_columns_can_point_forward():
    schema = parse("CREATE TABLE t (x INT REFERENCES u); CREATE TABLE u (id INT PRIMARY KEY);")
    assert schema.foreign_keys[0].to_columns == ["id"]


def test_reference_to_unknown_table_keeps_its_name():
    fk = parse("CREATE TABLE t (x INT REFERENCES missing);").foreign_keys[0]
    assert (fk.to_table, fk.to_columns) == ("missing", [])


# --- table constraints ---


def test_composite_primary_key():
    assert parse_table("a INT, b INT, PRIMARY KEY (a, b)").primary_key == ["a", "b"]


def test_named_primary_key():
    assert parse_table("a INT, CONSTRAINT pk PRIMARY KEY (a)").primary_key == ["a"]


def test_table_level_unique_marks_the_column():
    table = parse_table("a INT, b INT, UNIQUE (A)")
    assert [c.unique for c in table.columns] == [True, False]


def test_multi_column_unique_does_not_mark_either_column():
    table = parse_table("a INT, b INT, UNIQUE (a, b)")
    assert [c.unique for c in table.columns] == [False, False]


# --- errors ---


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("CREATE TABLE (x INT);", r"Expected a name but found '\(' at line 1, col 14"),
        ("CREATE TABLE t x INT);", r"Expected \( but found 'x' at line 1, col 16"),
        ("CREATE TABLE t (x @ INT);", r"Expected a column constraint but found '@' at line 1, col 19"),
        ("CREATE TABLE t (x INT", r"Expected a column constraint but found end of file at line 1, col 22"),
        ("CREATE TABLE t (x INT,);", r"Expected a name but found '\)' at line 1, col 23"),
        ("CREATE TABLE t (x INT NOT);", r"Expected NULL but found '\)' at line 1, col 26"),
        ("CREATE TABLE t (x INT PRIMARY);", r"Expected KEY but found '\)' at line 1, col 30"),
        ("CREATE TABLE t (x INT DEFAULT);", r"Expected a default value but found '\)' at line 1, col 30"),
        ("CREATE TABLE t (x INT CHECK (x > 0", r"Unclosed '\(' at line 1, col 29"),
        ("CREATE TABLE t (x INT REFERENCES u(id) ON DELETE y);", r"foreign key action but found 'y' at line 1, col 50"),
        ("CREATE TABLE t (x VARCHAR(10;", r"Unclosed '\(' at line 1, col 26"),
        ("CREATE TABLE t (x VARCHAR(10);", r"Expected a column constraint but found ';' at line 1, col 30"),
    ],
)
def test_errors_say_what_and_where(sql, message):
    with pytest.raises(ParseError, match=message):
        parse(sql)


def test_error_position_on_a_later_line():
    with pytest.raises(ParseError, match="line 4, col 1"):
        parse("CREATE TABLE t (\n  x INT,\n  y INT NOT\n);")


# --- ALTER TABLE ---


def parse_alter(action, setup="CREATE TABLE t (x INT, y INT); CREATE TABLE u (id INT PRIMARY KEY);"):
    return parse(f"{setup} ALTER TABLE t {action};")


def test_alter_add_foreign_key():
    fk = parse_alter("ADD FOREIGN KEY (x) REFERENCES u(id)").foreign_keys[0]
    assert (fk.from_table, fk.from_columns, fk.to_table, fk.to_columns) == ("t", ["x"], "u", ["id"])


def test_alter_add_named_foreign_key():
    assert parse_alter("ADD CONSTRAINT fk_x FOREIGN KEY (x) REFERENCES u(id) ON DELETE CASCADE").foreign_keys[0] == (
        ForeignKey("t", ["x"], "u", ["id"], name="fk_x", on_delete="CASCADE")
    )


def test_alter_add_several_actions():
    schema = parse_alter("ADD FOREIGN KEY (x) REFERENCES u(id), ADD FOREIGN KEY (y) REFERENCES u(id)")
    assert len(schema.foreign_keys) == 2


def test_alter_add_primary_key():
    assert parse_alter("ADD PRIMARY KEY (x, y)").tables[0].primary_key == ["x", "y"]


def test_alter_primary_key_does_not_repeat_columns():
    schema = parse("CREATE TABLE t (x INT PRIMARY KEY); ALTER TABLE t ADD PRIMARY KEY (x);")
    assert schema.tables[0].primary_key == ["x"]


def test_alter_add_unique():
    assert parse_alter("ADD UNIQUE (x)").tables[0].column("x").unique


def test_alter_add_check():
    assert parse_alter("ADD CONSTRAINT c CHECK (x > 0)").tables[0].checks == ["x > 0"]


@pytest.mark.parametrize("action", ["ADD z TEXT NOT NULL", "ADD COLUMN z TEXT NOT NULL", "ADD COLUMN IF NOT EXISTS z TEXT NOT NULL"])
def test_alter_add_column(action):
    column = parse_alter(action).tables[0].column("z")
    assert (column.type, column.nullable) == ("TEXT", False)


def test_alter_add_column_with_reference():
    assert parse_alter("ADD COLUMN z INT REFERENCES u(id)").foreign_keys[0].from_columns == ["z"]


@pytest.mark.parametrize("prefix", ["ONLY t", "IF EXISTS t", "IF EXISTS ONLY public.t", "public.t", '"t"', "[dbo].[t]", "T"])
def test_alter_table_name_forms(prefix):
    schema = parse(f"CREATE TABLE t (x INT); ALTER TABLE {prefix} ADD FOREIGN KEY (x) REFERENCES t(x);")
    assert len(schema.foreign_keys) == 1


def test_alter_with_check_before_add():
    assert len(parse_alter("WITH CHECK ADD CONSTRAINT f FOREIGN KEY (x) REFERENCES u (id)").foreign_keys) == 1


@pytest.mark.parametrize(
    "action",
    ["OWNER TO me", "DROP COLUMN x", "ENABLE ROW LEVEL SECURITY", "CHECK CONSTRAINT f", "RENAME TO v", "MODIFY x INT"],
)
def test_other_alter_actions_change_nothing(action):
    schema = parse_alter(action)
    assert schema.warnings == []
    assert schema.tables == parse("CREATE TABLE t (x INT, y INT); CREATE TABLE u (id INT PRIMARY KEY);").tables


def test_alter_unknown_table_warns():
    schema = parse("ALTER TABLE ghost ADD PRIMARY KEY (x);")
    assert "ghost" in schema.warnings[0]
    assert "line 1" in schema.warnings[0]


def test_alter_before_create_warns_and_keeps_going():
    schema = parse("ALTER TABLE t ADD PRIMARY KEY (x); CREATE TABLE t (x INT);")
    assert schema.tables[0].primary_key == []
    assert len(schema.warnings) == 1


def test_unreadable_alter_action_warns_and_keeps_going():
    schema = parse("CREATE TABLE t (x INT); ALTER TABLE t ADD @; CREATE TABLE u (y INT);")
    assert [t.name for t in schema.tables] == ["t", "u"]
    assert any("ALTER TABLE t" in w for w in schema.warnings)


def test_alter_column_set_not_null():
    assert parse_alter("ALTER COLUMN x SET NOT NULL").tables[0].column("x").nullable is False


def test_alter_column_set_default():
    assert parse_alter("ALTER COLUMN x SET DEFAULT 5").tables[0].column("x").default == "5"


def test_alter_column_add_identity():
    action = "ALTER COLUMN x ADD GENERATED ALWAYS AS IDENTITY (SEQUENCE NAME s START WITH 1 CACHE 1)"
    assert parse_alter(action).tables[0].column("x").auto_increment


def test_alter_column_default_from_a_sequence_is_auto_increment():
    column = parse_alter("ALTER COLUMN x SET DEFAULT nextval('s'::regclass)").tables[0].column("x")
    assert (column.auto_increment, column.default) == (True, None)


def test_alter_column_on_unknown_column_changes_nothing():
    assert parse_alter("ALTER COLUMN nope SET NOT NULL").warnings == []


# --- names ---


@pytest.mark.parametrize(
    "name",
    ["public.users", "db.public.users", "[dbo].[users]", '"public"."users"', "`shop`.`users`", "users", "'users'"],
)
def test_qualified_and_quoted_table_names(name):
    assert parse(f"CREATE TABLE {name} (x INT);").tables[0].name == "users"


def test_qualified_reference():
    fk = parse("CREATE TABLE public.u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES public.u(id));")
    assert fk.foreign_keys[0].to_table == "u"
    assert fk.warnings == []


@pytest.mark.parametrize("name", ["key", "action", "set", "no", "add", "update", "delete", "if", "on", "cascade"])
def test_non_reserved_keywords_can_be_column_names(name):
    assert parse_column(f"{name} INT").name == name


def test_keyword_table_name_keeps_its_spelling():
    assert parse("CREATE TABLE Action (x INT);").tables[0].name == "Action"


def test_foreign_key_can_reference_a_keyword_column():
    schema = parse("CREATE TABLE n (key INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES n(key));")
    assert schema.foreign_keys[0].to_columns == ["key"]


def test_same_table_twice_warns():
    schema = parse("CREATE TABLE t (x INT); CREATE TABLE T (y INT);")
    assert "more than once" in schema.warnings[0]


# --- statements in real files ---


@pytest.mark.parametrize("words", ["TEMP", "TEMPORARY", "UNLOGGED", "GLOBAL TEMPORARY", "OR REPLACE", "EXTERNAL"])
def test_create_table_qualifiers(words):
    assert parse(f"CREATE {words} TABLE t (x INT);").tables[0].name == "t"


@pytest.mark.parametrize(
    "rest",
    ["t AS SELECT 1", "t LIKE other", "t PARTITION OF parent FOR VALUES IN (1)", "t USING fts5(x)"],
)
def test_table_without_a_column_list_warns(rest):
    schema = parse(f"CREATE TABLE {rest}; CREATE TABLE u (x INT);")
    assert [t.name for t in schema.tables] == ["u"]
    assert "Skipped table t" in schema.warnings[0]


def test_unknown_characters_outside_tables_are_ignored():
    schema = parse("SET @a = @@b; SELECT $1 ? !; CREATE TABLE t (x INT);")
    assert [t.name for t in schema.tables] == ["t"]


def test_missing_semicolon_does_not_swallow_the_next_table():
    assert [t.name for t in parse("SET x = 1\nCREATE TABLE t (x INT)\nCREATE TABLE u (y INT);").tables] == ["t", "u"]


def test_function_body_does_not_end_a_statement_early():
    sql = "CREATE FUNCTION f() AS $$ BEGIN; it's; CREATE TABLE fake (x INT); END $$; CREATE TABLE t (x INT);"
    assert [t.name for t in parse(sql).tables] == ["t"]


def test_table_options_with_parentheses_are_skipped():
    assert len(parse("CREATE TABLE a (x INT) PARTITION BY RANGE (x); CREATE TABLE b (x INT);").tables) == 2


# --- column clauses ---


@pytest.mark.parametrize(
    "clause",
    ["AUTO_INCREMENT", "AUTOINCREMENT", "IDENTITY", "IDENTITY(1, 1)", "GENERATED ALWAYS AS IDENTITY",
     "GENERATED BY DEFAULT AS IDENTITY", "GENERATED BY DEFAULT AS IDENTITY (START WITH 10)"],
)
def test_auto_increment_forms(clause):
    column = parse_column(f"x INT {clause}")
    assert column.auto_increment
    assert column.type == "INT"


def test_default_from_a_sequence_is_auto_increment():
    column = parse_column("x INT DEFAULT nextval('s'::regclass) NOT NULL")
    assert (column.auto_increment, column.default, column.nullable) == (True, None, False)


def test_serial_is_just_a_type():
    assert not parse_column("x SERIAL").auto_increment


@pytest.mark.parametrize(
    "clause",
    ["COLLATE utf8mb4_bin", 'COLLATE pg_catalog."default"', "COMMENT 'it''s here'", "CHARACTER SET utf8",
     "CHARSET utf8", "ON UPDATE CURRENT_TIMESTAMP", "ON CONFLICT REPLACE", "GENERATED ALWAYS AS (1 + 1) STORED",
     "AS (1 + 1) PERSISTED", "NOT DEFERRABLE", "DEFERRABLE INITIALLY DEFERRED", "NOT FOR REPLICATION", "CHECK (x > 0) NOT ENFORCED"],
)
def test_clauses_that_do_not_affect_the_diagram(clause):
    table = parse_table(f"x VARCHAR(10) {clause} NOT NULL, y INT")
    assert table.columns[0].type == "VARCHAR(10)"
    assert table.columns[0].nullable is False
    assert [c.name for c in table.columns] == ["x", "y"]
    assert parse(f"CREATE TABLE t (x VARCHAR(10) {clause} NOT NULL);").warnings == []


def test_unknown_keyword_clause_warns_and_keeps_going():
    schema = parse("CREATE TABLE t (x INT ACTION(5) NOT NULL);")
    assert schema.tables[0].columns[0].nullable is False
    assert "Ignored ACTION on column t.x (line 1)" in schema.warnings


def test_key_on_a_column_means_primary_key():
    assert parse_table("x INT KEY").primary_key == ["x"]


def test_unique_key_on_a_column():
    assert parse_column("x INT UNIQUE KEY").unique


def test_column_with_no_type():
    table = parse_table("x, y PRIMARY KEY, z NOT NULL")
    assert [c.type for c in table.columns] == ["", "", ""]
    assert table.primary_key == ["y"]
    assert table.columns[2].nullable is False


@pytest.mark.parametrize(
    "type_text",
    ["TEXT[]", "INT[3]", "INT[][]", "public.citext", "INT UNSIGNED", "SET('a', 'b')", "nvarchar(max)", "datetime2(7)"],
)
def test_dialect_types(type_text):
    assert parse_column(f"x {type_text}").type == type_text


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("-1", "-1"),
        ("+1.5", "+1.5"),
        ("1 + 2", "1 + 2"),
        ("-1.5e2", "-1.5e2"),
        ("'x'::text", "'x'::text"),
        ("'{}'::text[]", "'{}'::text[]"),
        ("ARRAY[1, 2]", "ARRAY[1, 2]"),
        ("N'x'", "N'x'"),
        ("((0))", "((0))"),
        ("a || b", "a || b"),
    ],
)
def test_default_expressions(sql, expected):
    assert parse_column(f"x INT DEFAULT {sql}").default == expected


def test_default_stops_at_column_attributes():
    column = parse_column("x INT DEFAULT 0 AUTO_INCREMENT COMMENT 'c'")
    assert (column.default, column.auto_increment) == ("0", True)


# --- MySQL indexes ---


@pytest.mark.parametrize(
    "item",
    ["KEY idx (a)", "KEY (a)", "INDEX idx (a)", "INDEX (a, b)", "FULLTEXT KEY idx (a)", "FULLTEXT idx (a)",
     "SPATIAL INDEX idx (a)", "KEY idx (a(10))", "KEY idx (a) USING BTREE", "KEY `idx` (`a`)"],
)
def test_indexes_are_not_columns(item):
    assert [c.name for c in parse_table(f"a INT, b INT, {item}").columns] == ["a", "b"]


@pytest.mark.parametrize("name", ["key", "index", "fulltext", "spatial"])
def test_columns_named_like_index_words(name):
    assert [c.name for c in parse_table(f"{name} VARCHAR(10), {name}2 INT").columns] == [name, f"{name}2"]


def test_quoted_index_word_is_a_column():
    assert parse_column("[index] [varchar](max)").name == "index"


# --- table constraint forms ---


@pytest.mark.parametrize(
    "item",
    ["PRIMARY KEY CLUSTERED (a ASC)", "PRIMARY KEY USING BTREE (a)", "PRIMARY KEY (a) USING BTREE",
     "PRIMARY KEY (a) WITH (PAD_INDEX = OFF) ON [PRIMARY]", "CONSTRAINT [pk] PRIMARY KEY NONCLUSTERED ([a] DESC)",
     "PRIMARY KEY (a(10))", "PRIMARY KEY (a) NOT DEFERRABLE"],
)
def test_primary_key_forms(item):
    assert parse_table(f"a INT, {item}").primary_key == ["a"]


@pytest.mark.parametrize(
    "item",
    ["UNIQUE KEY uq (a)", "UNIQUE INDEX uq (a)", "UNIQUE uq (a)", "UNIQUE NONCLUSTERED (a ASC)", "CONSTRAINT c UNIQUE (a)"],
)
def test_unique_forms(item):
    assert parse_table(f"a INT, {item}").columns[0].unique


def test_foreign_key_with_mysql_index_name():
    assert parse_table("a INT, FOREIGN KEY idx (a) REFERENCES u (id)").foreign_keys[0].from_columns == ["a"]


@pytest.mark.parametrize(
    "tail",
    ["MATCH FULL", "DEFERRABLE", "NOT VALID", "NOT FOR REPLICATION", "MATCH SIMPLE ON DELETE CASCADE"],
)
def test_foreign_key_tails(tail):
    table = parse_table(f"a INT, FOREIGN KEY (a) REFERENCES u (id) {tail}, b INT")
    assert [c.name for c in table.columns] == ["a", "b"]
    assert len(table.foreign_keys) == 1


def test_multi_column_unique_is_kept():
    table = parse_table("a INT, b INT, UNIQUE (a, b)")
    assert table.unique_sets == [["a", "b"]]


def test_single_column_unique_before_its_column():
    table = parse_table("UNIQUE (a), a INT")
    assert table.columns[0].unique
    assert table.unique_sets == []


def test_exclude_constraint_warns():
    schema = parse("CREATE TABLE t (a INT, EXCLUDE USING gist (a WITH =));")
    assert [c.name for c in schema.tables[0].columns] == ["a"]
    assert "EXCLUDE" in schema.warnings[0]


def test_unknown_named_constraint_warns():
    schema = parse("CREATE TABLE t (a INT, CONSTRAINT c EXCLUDE USING gist (a WITH =));")
    assert [c.name for c in schema.tables[0].columns] == ["a"]
    assert "Skipped constraint" in schema.warnings[0]


# --- reference warnings ---


def test_clean_schema_has_no_warnings():
    schema = parse("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES u(id));")
    assert schema.warnings == []


def test_reference_to_missing_table_warns():
    assert parse("CREATE TABLE t (x INT REFERENCES ghost(id));").warnings == [
        "t.x references ghost, which isn't in this file",
    ]


def test_reference_to_table_without_primary_key_warns():
    schema = parse("CREATE TABLE u (id INT); CREATE TABLE t (x INT REFERENCES u);")
    assert schema.warnings == ["t.x references u, which has no primary key"]


def test_reference_to_missing_column_warns():
    schema = parse("CREATE TABLE u (id INT); CREATE TABLE t (x INT REFERENCES u(nope));")
    assert schema.warnings == ["t.x references unknown column u.nope"]


def test_foreign_key_on_missing_column_warns():
    schema = parse("CREATE TABLE u (id INT); CREATE TABLE t (x INT, FOREIGN KEY (nope) REFERENCES u(id));")
    assert schema.warnings == ["Foreign key on t uses unknown column nope"]


def test_mismatched_column_counts_warn():
    schema = parse("CREATE TABLE u (a INT, b INT); CREATE TABLE t (x INT, FOREIGN KEY (x) REFERENCES u(a, b));")
    assert schema.warnings == ["t.x doesn't match the number of columns in u"]


def test_reference_case_differences_do_not_warn():
    schema = parse("CREATE TABLE Users (Id INT PRIMARY KEY); CREATE TABLE t (X INT, FOREIGN KEY (x) REFERENCES USERS(ID));")
    assert schema.warnings == []


# --- found by running the real Sakila schema ---


def test_versioned_comment_holds_a_column():
    # The form used by Sakila's address table.
    table = parse_table("""
        phone VARCHAR(20) NOT NULL,
        /*!50705 location GEOMETRY */ /*!80003 SRID 0 */ /*!50705 NOT NULL,*/
        last_update TIMESTAMP,
        /*!50705 SPATIAL KEY `idx_location` (location),*/
        PRIMARY KEY (phone)
    """)
    assert [c.name for c in table.columns] == ["phone", "location", "last_update"]
    assert table.columns[1].type == "GEOMETRY"
    assert table.columns[1].nullable is False
    assert table.primary_key == ["phone"]


def test_srid_without_a_comment():
    column = parse_column("x GEOMETRY SRID 4326 NOT NULL")
    assert (column.type, column.nullable) == ("GEOMETRY", False)


@pytest.mark.parametrize("delimiter", ["//", "$$", ";;", "|"])
def test_table_inside_a_routine_is_not_in_the_schema(delimiter):
    sql = f"""
CREATE TABLE before_it (x INT);
DELIMITER {delimiter}
CREATE PROCEDURE p()
BEGIN
    CREATE TEMPORARY TABLE tmp (x INT);
    DROP TABLE tmp;
END {delimiter}
DELIMITER ;
CREATE TABLE after_it (x INT);
"""
    schema = parse(sql)
    assert [t.name for t in schema.tables] == ["before_it", "after_it"]
    assert schema.warnings == []


def test_several_delimiter_blocks():
    sql = """
DELIMITER $$
CREATE FUNCTION f() BEGIN RETURN 1; END $$
DELIMITER ;

DELIMITER $$
CREATE FUNCTION g() BEGIN CREATE TABLE fake (x INT); END $$
DELIMITER ;

CREATE TABLE t (x INT);
"""
    assert [t.name for t in parse(sql).tables] == ["t"]


def test_delimiter_reset_alone_changes_nothing():
    assert [t.name for t in parse("DELIMITER ;\nCREATE TABLE t (x INT);").tables] == ["t"]


def test_delimiter_reset_at_the_end_of_a_file():
    assert parse("CREATE TABLE t (x INT);\nDELIMITER ;").warnings == []


def test_delimiter_never_reset_warns():
    schema = parse("CREATE TABLE t (x INT);\nDELIMITER //\nCREATE TABLE lost (x INT);")
    assert [t.name for t in schema.tables] == ["t"]
    assert "never set back" in schema.warnings[0]


def test_statement_without_a_semicolon_stops_at_delimiter():
    sql = "SET x = 1\nDELIMITER //\nCREATE TABLE fake (x INT);\n//\nDELIMITER ;\nCREATE TABLE t (x INT);"
    assert [t.name for t in parse(sql).tables] == ["t"]


def test_column_named_delimiter():
    assert parse_column("delimiter INT").name == "delimiter"
