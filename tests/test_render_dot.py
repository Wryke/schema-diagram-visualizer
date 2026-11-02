"""Phase 1 tests. Delete the pytestmark line when you start the renderer."""

import pytest

from schemadiagram.model import Column, ForeignKey, Schema, Table
from schemadiagram.render_dot import escape, to_dot

pytestmark = pytest.mark.skip(reason="Phase 1: delete this line when you start the renderer")


def test_escape_html_characters():
    assert escape("salary > 0 & x < 5") == "salary &gt; 0 &amp; x &lt; 5"


def test_each_table_becomes_a_node():
    schema = Schema(tables=[Table("users", [Column("id", "INT")])])
    dot = to_dot(schema)
    assert dot.startswith("digraph")
    assert "users" in dot


def test_self_reference_edge():
    schema = Schema(tables=[
        Table(
            "employees",
            [Column("id", "INT"), Column("manager_id", "INT")],
            [ForeignKey("employees", ["manager_id"], "employees", ["id"])],
        ),
    ])
    assert "employees:manager_id -> employees:id" in to_dot(schema)
