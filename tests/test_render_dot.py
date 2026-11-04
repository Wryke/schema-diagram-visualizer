"""Phase 1 tests. Delete the pytestmark line when you start the renderer."""

from schemadiagram.model import Column, ForeignKey, Schema, Table
from schemadiagram.render_dot import escape, to_dot

# pytestmark = pytest.mark.skip(reason="Phase 1: delete this line when you start the renderer")


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


def test_composite_foreign_key_draws_every_column_pair():
    schema = Schema(tables=[
        Table("order_lines", [Column("order_id", "INT"), Column("line_no", "INT")]),
        Table("shipments", [Column("order_id", "INT"), Column("line_no", "INT")],
              [ForeignKey("shipments", ["order_id", "line_no"], "order_lines", ["order_id", "line_no"])]),
    ])
    dot = to_dot(schema)
    assert "shipments:order_id -> order_lines:order_id" in dot
    assert "shipments:line_no -> order_lines:line_no" in dot
    
    
def edge_lines(dot):
    """The edge lines of a DOT string, with indentation removed."""
    return [line.strip() for line in dot.splitlines() if "->" in line]


def test_edges_are_separate_dot_lines():
    schema = Schema(tables=[
        Table("users", [Column("id", "INT")]),
        Table("employees", [Column("id", "INT"), Column("user_id", "INT")],
              [ForeignKey("employees", ["user_id"], "users", ["id"])]),
    ])
    assert edge_lines(to_dot(schema)) == ["employees:user_id -> users:id;"]


def test_schema_without_foreign_keys_has_no_edges():
    schema = Schema(tables=[Table("users", [Column("id", "INT")])])
    assert edge_lines(to_dot(schema)) == []


def composite_schema(fk_name=None):
    return Schema(tables=[
        Table("order_lines", [Column("order_id", "INT"), Column("line_no", "INT")]),
        Table("shipments", [Column("order_id", "INT"), Column("line_no", "INT")],
              [ForeignKey("shipments", ["order_id", "line_no"], "order_lines", ["order_id", "line_no"],
                          name=fk_name)]),
    ])


def test_composite_fk_arrows_share_one_label():
    lines = edge_lines(to_dot(composite_schema()))
    assert len(lines) == 2
    assert all('label="fk 1"' in line for line in lines)


def test_composite_fk_uses_constraint_name():
    lines = edge_lines(to_dot(composite_schema(fk_name="fk_line")))
    assert all('label="fk_line"' in line for line in lines)


def test_single_column_fk_has_no_label():
    schema = Schema(tables=[
        Table("employees", [Column("id", "INT"), Column("manager_id", "INT")],
              [ForeignKey("employees", ["manager_id"], "employees", ["id"])]),
    ])
    assert "label=" not in edge_lines(to_dot(schema))[0]