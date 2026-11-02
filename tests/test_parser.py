"""Phase 3 tests. Delete the pytestmark line when you start the parser."""

import pytest

from schemadiagram.parser import parse

pytestmark = pytest.mark.skip(reason="Phase 3: delete this line when you start the parser")


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


# TODO: a test that parses examples/basic.sql and compares it to a hand-built Schema
