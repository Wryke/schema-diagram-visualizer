"""Phase 1 and 5 tests: Schema in, DOT text out."""

import re
import shutil
from pathlib import Path

import graphviz
import pytest

from schemadiagram.model import Column, ForeignKey, Schema, Table
from schemadiagram.parser import parse
from schemadiagram.render_dot import dot_id, escape, rank_separation, table_label, to_dot

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_escape_html_characters():
    assert escape("salary > 0 & x < 5") == "salary &gt; 0 &amp; x &lt; 5"


def test_each_table_becomes_a_node():
    schema = Schema(tables=[Table("users", [Column("id", "INT")])])
    dot = to_dot(schema)
    assert dot.startswith("digraph")
    assert "users" in dot


def test_dpi_line_only_when_asked():
    schema = Schema(tables=[Table("users", [Column("id", "INT")])])
    assert "dpi" not in to_dot(schema)
    assert "graph [dpi=200];" in to_dot(schema, dpi=200)


def test_self_reference_edge():
    schema = Schema(tables=[
        Table(
            "employees",
            [Column("id", "INT"), Column("manager_id", "INT")],
            [ForeignKey("employees", ["manager_id"], "employees", ["id"])],
        ),
    ])
    assert "employees:manager_id:e -> employees:id:e" in to_dot(schema)


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


def edge_line(sql):
    """Parse SQL with exactly one foreign key and return its DOT edge line."""
    lines = edge_lines(to_dot(parse(sql)))
    assert len(lines) == 1
    return lines[0]


def label_rows(table):
    """The text of each row in a table's label, with the HTML tags removed."""
    return [re.sub(r"<[^>]+>", "", row) for row in table_label(table).splitlines()[1:-1]]


def test_edges_are_separate_dot_lines():
    schema = Schema(tables=[
        Table("users", [Column("id", "INT")]),
        Table("employees", [Column("id", "INT"), Column("user_id", "INT", nullable=False)],
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


# --- column rows ---


def test_primary_key_marker():
    table = Table("t", [Column("id", "INT"), Column("name", "TEXT")], primary_key=["id"])
    assert label_rows(table)[1].startswith("PK  id")
    assert "PK" not in label_rows(table)[2]


def test_foreign_key_marker():
    table = Table("t", [Column("u", "INT")], [ForeignKey("t", ["u"], "users", ["id"])])
    assert label_rows(table)[1].startswith("FK  u")


def test_column_in_primary_and_foreign_key_gets_both_markers():
    table = Table("t", [Column("u", "INT")], [ForeignKey("t", ["u"], "users", ["id"])], primary_key=["u"])
    assert label_rows(table)[1].startswith("PK,FK  u")


def test_every_column_of_a_composite_primary_key_is_marked():
    table = Table("t", [Column("a", "INT"), Column("b", "INT")], primary_key=["a", "b"])
    assert [row[:2] for row in label_rows(table)[1:]] == ["PK", "PK"]


def test_markers_ignore_case():
    table = Table("t", [Column("ID", "INT")], primary_key=["id"])
    assert label_rows(table)[1].startswith("PK")


def test_no_gap_when_a_table_has_no_markers():
    assert label_rows(Table("t", [Column("x", "INT")]))[1] == "x  INT"


@pytest.mark.parametrize(
    ("column", "note"),
    [
        (Column("x", "INT", nullable=False), "NOT NULL"),
        (Column("x", "INT", unique=True), "UNIQUE"),
        (Column("x", "INT", default="0"), "DEFAULT 0"),
        (Column("x", "TEXT", default="'member'"), "DEFAULT 'member'"),
    ],
)
def test_column_notes(column, note):
    assert label_rows(Table("t", [column]))[1].endswith(note)


def test_notes_combine_on_one_row():
    column = Column("x", "INT", nullable=False, unique=True, default="0")
    assert label_rows(Table("t", [column]))[1].endswith("NOT NULL UNIQUE DEFAULT 0")


def test_column_without_constraints_has_no_notes():
    assert label_rows(Table("t", [Column("x", "INT")]))[1] == "x  INT"


def test_rows_line_up():
    table = Table("t", [Column("id", "INT", nullable=False), Column("long_name", "VARCHAR(255)", nullable=False)],
                  primary_key=["id"])
    first, second = label_rows(table)[1:]
    assert first.index("INT") == second.index("VARCHAR")
    assert first.index("NOT NULL") == second.index("NOT NULL")
    assert first.index("id") == second.index("long_name")


def test_every_column_keeps_its_port():
    label = table_label(Table("t", [Column("a", "INT"), Column("b", "INT")], primary_key=["a"]))
    assert 'port="a"' in label
    assert 'port="b"' in label


def test_table_with_no_columns():
    assert label_rows(Table("t")) == ["t"]


# --- CHECK footer ---


def test_no_footer_without_checks():
    assert "CHECK" not in table_label(Table("t", [Column("x", "INT")]))


def test_column_check_goes_in_the_footer():
    rows = label_rows(Table("t", [Column("x", "INT", check="x = 1")]))
    assert rows[-1] == "CHECK (x = 1)"
    assert "CHECK" not in rows[1]


def test_column_and_table_checks_share_one_footer():
    table = Table("t", [Column("x", "INT", check="x = 1")], checks=["x = 2"])
    assert table_label(table).count("bgcolor") == 2  # the header and one footer
    assert label_rows(table)[-1] == "CHECK (x = 1)CHECK (x = 2)"


def test_check_is_escaped():
    label = table_label(Table("t", [Column("x", "INT", check="x > 0 & x < 5")]))
    assert "CHECK (x &gt; 0 &amp; x &lt; 5)" in label


def test_default_is_escaped():
    assert "DEFAULT &lt;none&gt;" in table_label(Table("t", [Column("x", "TEXT", default="<none>")]))


def test_long_check_wraps():
    # Uses "=" because the wrap width counts the text before escaping, and ">" gets longer when escaped.
    label = table_label(Table("t", [Column("x", "INT")], checks=[" AND ".join(["x = 100000"] * 10)]))
    footer = label.split('point-size="10">')[1].split("</font>")[0]
    lines = [line for line in footer.split('<br align="left"/>') if line]
    assert len(lines) > 1
    assert all(len(line) <= 50 for line in lines)


# --- relationships ---


def test_edge_defaults_are_many_to_one():
    dot = to_dot(Schema(tables=[Table("t", [Column("x", "INT")])]))
    assert "edge [dir=both, arrowtail=crow, arrowhead=tee" in dot


def test_required_foreign_key_is_solid():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT NOT NULL REFERENCES u(id));")
    assert line == "t:x -> u:id;"


def test_nullable_foreign_key_is_dashed():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES u(id));")
    assert "style=dashed" in line


def test_primary_key_column_is_not_optional_even_without_not_null():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT PRIMARY KEY REFERENCES u(id));")
    assert "style=dashed" not in line


def test_composite_key_is_optional_if_any_column_is_nullable():
    sql = """
        CREATE TABLE u (a INT, b INT, PRIMARY KEY (a, b));
        CREATE TABLE t (x INT NOT NULL, y INT, FOREIGN KEY (x, y) REFERENCES u(a, b));
    """
    assert all("style=dashed" in line for line in edge_lines(to_dot(parse(sql))))


def test_unique_foreign_key_is_one_to_one():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT NOT NULL UNIQUE REFERENCES u(id));")
    assert "arrowtail=tee" in line


def test_foreign_key_that_is_the_whole_primary_key_is_one_to_one():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT PRIMARY KEY REFERENCES u(id));")
    assert "arrowtail=tee" in line


def test_foreign_key_that_is_part_of_the_primary_key_is_many_to_one():
    sql = """
        CREATE TABLE u (id INT PRIMARY KEY);
        CREATE TABLE t (x INT REFERENCES u(id), y INT, PRIMARY KEY (x, y));
    """
    assert "arrowtail" not in edge_line(sql)


def test_one_to_one_composite_keeps_all_its_attributes():
    sql = """
        CREATE TABLE u (a INT, b INT, PRIMARY KEY (a, b));
        CREATE TABLE t (x INT, y INT, PRIMARY KEY (x, y), FOREIGN KEY (x, y) REFERENCES u(a, b));
    """
    line = edge_lines(to_dot(parse(sql)))[0]
    assert "arrowtail=tee" in line
    assert 'label="fk 1"' in line


def test_each_composite_key_gets_its_own_color():
    sql = """
        CREATE TABLE u (a INT, b INT, PRIMARY KEY (a, b));
        CREATE TABLE t (w INT, x INT, y INT, z INT,
                        FOREIGN KEY (w, x) REFERENCES u(a, b),
                        FOREIGN KEY (y, z) REFERENCES u(a, b));
    """
    colors = [re.search(r'color="(\w+)"', line).group(1) for line in edge_lines(to_dot(parse(sql)))]
    assert colors[0] == colors[1]
    assert colors[2] == colors[3]
    assert colors[0] != colors[2]


def test_reference_uses_the_spelling_the_table_declared():
    line = edge_line("CREATE TABLE Users (Id INT PRIMARY KEY); CREATE TABLE t (x INT NOT NULL REFERENCES USERS(ID));")
    assert line == "t:x -> Users:Id;"


def test_foreign_key_column_uses_the_spelling_the_column_declared():
    sql = "CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (Col INT NOT NULL, FOREIGN KEY (COL) REFERENCES u(id));"
    assert edge_line(sql) == "t:Col -> u:id;"


def test_reference_to_unknown_table_keeps_its_name():
    assert edge_line("CREATE TABLE t (x INT NOT NULL REFERENCES missing(id));") == "t:x -> missing;"


# --- self-reference loops ---


def self_loop(sql):
    """The DOT line of the self-reference on table e."""
    return next(line for line in edge_lines(to_dot(parse(sql))) if line.startswith("e:m"))


def test_loop_stays_right_with_nothing_on_the_right():
    assert self_loop("CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id));").startswith("e:m:e -> e:id:e")


def test_loop_moves_left_when_a_parent_is_on_the_right():
    sql = """
        CREATE TABLE u (id INT PRIMARY KEY);
        CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), u INT REFERENCES u(id));
    """
    assert self_loop(sql).startswith("e:m:w -> e:id:w")


def test_loop_stays_right_when_only_children_point_at_the_table():
    sql = """
        CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id));
        CREATE TABLE c (id INT REFERENCES e(id));
    """
    assert self_loop(sql).startswith("e:m:e -> e:id:e")


def test_loop_in_a_cycle_follows_declaration_order():
    later = """
        CREATE TABLE w (id INT PRIMARY KEY, boss INT REFERENCES e(id));
        CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), w INT REFERENCES w(id));
    """
    earlier = """
        CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), w INT REFERENCES w(id));
        CREATE TABLE w (id INT PRIMARY KEY, boss INT REFERENCES e(id));
    """
    assert self_loop(later).startswith("e:m:e")
    assert self_loop(earlier).startswith("e:m:w")


def test_loop_moves_left_for_a_parent_missing_from_the_file():
    sql = "CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), u INT REFERENCES missing(id));"
    assert self_loop(sql).startswith("e:m:w")


def test_only_self_references_get_a_compass_side():
    line = edge_line("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT NOT NULL REFERENCES u(id));")
    assert ":e" not in line
    assert ":w" not in line


# --- model helpers ---


def test_table_is_foreign_key_covers_every_column_and_ignores_case():
    table = Table("t", [], [ForeignKey("t", ["a", "b"], "u", ["c", "d"])])
    assert table.is_foreign_key("A")
    assert table.is_foreign_key("b")
    assert not table.is_foreign_key("c")


# --- real Graphviz output ---


def svg_of(sql):
    return graphviz.Source(to_dot(parse(sql))).pipe(format="svg", encoding="utf-8")


@needs_graphviz
@pytest.mark.parametrize("name", ["basic.sql", "store.sql"])
def test_examples_draw_one_box_per_table_and_every_arrow(name):
    schema = parse((EXAMPLES / name).read_text())
    svg = svg_of((EXAMPLES / name).read_text())
    arrows = sum(len(fk.from_columns) for fk in schema.foreign_keys)
    assert svg.count('class="node"') == len(schema.tables)
    assert svg.count('class="edge"') == arrows


def test_store_example_is_the_ten_plus_table_schema():
    assert len(parse((EXAMPLES / "store.sql").read_text()).tables) >= 10


@needs_graphviz
def test_case_mismatch_does_not_draw_a_second_box():
    svg = svg_of("CREATE TABLE Users (Id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES USERS(ID));")
    assert svg.count('class="node"') == 2


@needs_graphviz
def test_special_characters_reach_the_drawing():
    svg = svg_of("CREATE TABLE t (x INT DEFAULT 1 CHECK (x > 0 AND x <> 5), y TEXT DEFAULT 'a & b');")
    assert "x &gt; 0 AND x &lt;&gt; 5" in svg
    assert "a &amp; b" in svg


# --- names DOT can't read plainly ---


@pytest.mark.parametrize("name", ["users", "_x", "a1", "Order_Items", "caf\u00e9"])
def test_plain_names_stay_unquoted(name):
    assert dot_id(name) == name


@pytest.mark.parametrize(
    ("name", "quoted"),
    [
        ("my table", '"my table"'),
        ("a-b", '"a-b"'),
        ("1a", '"1a"'),
        ("a.b", '"a.b"'),
        ("", '""'),
        ('a"b', '"a\\"b"'),
        ("node", '"node"'),
        ("EDGE", '"EDGE"'),
        ("Graph", '"Graph"'),
        ("digraph", '"digraph"'),
        ("subgraph", '"subgraph"'),
        ("strict", '"strict"'),
    ],
)
def test_other_names_are_quoted(name, quoted):
    assert dot_id(name) == quoted


def test_edges_quote_table_and_column_names():
    sql = 'CREATE TABLE node ("my id" INT PRIMARY KEY); CREATE TABLE "a b" (x INT NOT NULL REFERENCES node("my id"));'
    assert edge_line(sql) == '"a b":x -> "node":"my id";'


@needs_graphviz
@pytest.mark.parametrize(
    "name",
    ['"my table"', "[a-b]", "node", "edge", "graph", "digraph", "subgraph", "strict", '"1st"', '"a.b"', '"a""b"', "`x:y`", '"<b>&"'],
)
def test_awkward_table_names_draw_one_box_each(name):
    sql = f"CREATE TABLE {name} (id INT PRIMARY KEY, parent INT NOT NULL); CREATE TABLE t (x INT NOT NULL REFERENCES {name}(id));"
    svg = svg_of(sql)
    assert svg.count('class="node"') == 2
    assert svg.count('class="edge"') == 1


@needs_graphviz
@pytest.mark.parametrize("name", ["e", "n", "s", "w", "c", "ne", "_", '"my col"', "node", '"a:b"'])
def test_awkward_column_names_keep_their_arrow(name):
    sql = f"CREATE TABLE u ({name} INT PRIMARY KEY, other INT); CREATE TABLE t (x INT NOT NULL REFERENCES u({name}));"
    assert svg_of(sql).count('class="edge"') == 1


# --- references that can't be fully resolved ---


def test_missing_table_gets_a_dashed_box():
    dot = to_dot(parse("CREATE TABLE t (x INT REFERENCES ghost(id));"))
    assert 'ghost [label="ghost", shape=box, style=dashed];' in dot


def test_missing_table_gets_one_box_for_many_references():
    dot = to_dot(parse("CREATE TABLE t (x INT REFERENCES ghost(id), y INT REFERENCES ghost(id));"))
    assert dot.count("shape=box") == 1


def test_defined_tables_get_no_dashed_box():
    assert "shape=box" not in to_dot(parse("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES u(id));"))


def test_missing_table_with_dot_keyword_name_is_quoted():
    dot = to_dot(parse("CREATE TABLE t (x INT NOT NULL REFERENCES node(id));"))
    assert '"node" [label="node", shape=box' in dot
    assert 't:x -> "node";' in dot


def test_reference_without_a_primary_key_points_at_the_table():
    sql = "CREATE TABLE u (id INT); CREATE TABLE t (x INT NOT NULL REFERENCES u);"
    assert edge_line(sql) == "t:x -> u;"


def test_reference_to_missing_column_points_at_the_table():
    sql = "CREATE TABLE u (id INT); CREATE TABLE t (x INT NOT NULL REFERENCES u(nope));"
    assert edge_line(sql) == "t:x -> u;"


@needs_graphviz
def test_unresolved_references_draw_without_graphviz_warnings(capfd):
    sql = """
        CREATE TABLE u (id INT);
        CREATE TABLE t (a INT REFERENCES ghost(id), b INT REFERENCES u, c INT REFERENCES u(nope));
    """
    svg = svg_of(sql)
    assert svg.count('class="edge"') == 3
    assert svg.count('class="node"') == 3
    assert capfd.readouterr().err == ""


# --- new markers ---


def test_auto_increment_note():
    assert label_rows(Table("t", [Column("x", "INT", auto_increment=True, nullable=False)]))[1] == "x  INT  AUTO NOT NULL"


def test_multi_column_unique_goes_in_the_footer():
    table = Table("t", [Column("a", "INT"), Column("b", "INT")], unique_sets=[["a", "b"]])
    assert label_rows(table)[-1] == "UNIQUE (a, b)"


def test_multi_column_unique_foreign_key_is_one_to_one():
    sql = """
        CREATE TABLE u (a INT, b INT, PRIMARY KEY (a, b));
        CREATE TABLE t (x INT NOT NULL, y INT NOT NULL, UNIQUE (y, x), FOREIGN KEY (x, y) REFERENCES u(a, b));
    """
    assert all("arrowtail=tee" in line for line in edge_lines(to_dot(parse(sql))))


def test_foreign_key_in_a_larger_unique_set_is_many_to_one():
    sql = """
        CREATE TABLE u (a INT PRIMARY KEY);
        CREATE TABLE t (x INT NOT NULL REFERENCES u(a), y INT, UNIQUE (x, y));
    """
    assert "arrowtail" not in edge_line(sql)


# --- room for loops ---


def test_no_loop_uses_the_normal_separation():
    assert rank_separation(parse("CREATE TABLE u (id INT PRIMARY KEY); CREATE TABLE t (x INT REFERENCES u(id));")) == 1.2


def test_loop_with_a_free_side_uses_the_normal_separation():
    schema = parse("CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), a_long_column_name_here VARCHAR(255));")
    assert rank_separation(schema) == 1.2


def test_loop_with_tables_on_both_sides_widens_the_separation():
    schema = parse("""
        CREATE TABLE p (id INT PRIMARY KEY);
        CREATE TABLE e (id INT PRIMARY KEY, m INT REFERENCES e(id), p INT REFERENCES p(id),
                        a_long_column_name_here VARCHAR(255) NOT NULL DEFAULT 'something quite long');
        CREATE TABLE c (id INT REFERENCES e(id));
    """)
    assert rank_separation(schema) > 2
