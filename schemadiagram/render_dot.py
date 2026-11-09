"""Phase 1 and 5: turn a Schema into Graphviz DOT text, and render it.

This file knows about Graphviz but nothing about SQL text or tokens.
"""

import re
import textwrap
from pathlib import Path

import graphviz

from schemadiagram.model import Column, ForeignKey, Schema, Table

# Colors for composite foreign keys; cycles if there are more than four.
COMPOSITE_COLORS = ["darkgreen", "purple", "darkorange", "navy"]

HEADER_COLOR = "lightblue"
FOOTER_COLOR = "lightyellow"
FONT = "Courier New"

# Longer CHECK rules wrap onto more lines, so one long rule can't make a table huge.
CHECK_WRAP_WIDTH = 50

# A name DOT can read without quotes. Anything else, and DOT's own keywords, need them.
PLAIN_DOT_ID = re.compile(r"[^\W\d]\w*")
DOT_KEYWORDS = {"node", "edge", "graph", "digraph", "subgraph", "strict"}

# Inches between ranks of tables, and the rough width of one character in the 12pt font.
RANK_SEPARATION = 1.2
CHAR_WIDTH = 0.1


def escape(text: str) -> str:
    """Escape text for use inside an HTML-like label (& < > ")."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")


def dot_id(name: str) -> str:
    """A table or column name as a DOT identifier, quoted if it needs to be: "my table", "node"."""
    if PLAIN_DOT_ID.fullmatch(name) and name.lower() not in DOT_KEYWORDS:
        return name
    return '"' + name.replace('"', '\\"') + '"'


def column_marker(table: Table, column: Column) -> str:
    """PK and/or FK, for the first part of a column's row."""
    markers = []
    if table.is_primary_key(column.name):
        markers.append("PK")
    if table.is_foreign_key(column.name):
        markers.append("FK")
    return ",".join(markers)


def column_notes(column: Column) -> str:
    """The constraints written on a column, for the last part of its row."""
    notes = []
    if column.auto_increment:
        notes.append("AUTO")
    if not column.nullable:
        notes.append("NOT NULL")
    if column.unique:
        notes.append("UNIQUE")
    if column.default is not None:
        notes.append(f"DEFAULT {column.default}")
    return " ".join(notes)


def row_texts(table: Table) -> list[str]:
    """Each column's text, padded so the parts line up in a monospace font."""
    cells = [(column_marker(table, c), c.name, c.type) for c in table.columns]
    widths = [max((len(cell[i]) for cell in cells), default=0) for i in range(3)]

    rows = []
    for column, cell in zip(table.columns, cells):
        # A table with no PK or FK has an empty first part, which shouldn't leave a gap.
        parts = [text.ljust(width) for text, width in zip(cell, widths) if width]
        parts.append(column_notes(column))
        rows.append("  ".join(parts).rstrip())
    return rows


def column_rows(table: Table) -> list[str]:
    """One <tr> per column. Each row is a single cell, so an arrow can attach
    to either end of the row without crossing any text.
    """
    return [
        f'<tr><td port="{escape(column.name)}" align="left">{escape(text)}</td></tr>'
        for column, text in zip(table.columns, row_texts(table))
    ]


def footer_rows(table: Table) -> list[str]:
    """A footer row listing the rules that don't fit on one column, or nothing if there are none."""
    rules = [f"CHECK ({c.check})" for c in table.columns if c.check is not None]
    rules += [f"CHECK ({check})" for check in table.checks]
    rules += [f"UNIQUE ({', '.join(names)})" for names in table.unique_sets]
    if not rules:
        return []

    lines = []
    for rule in rules:
        lines.extend(textwrap.wrap(rule, CHECK_WRAP_WIDTH, subsequent_indent="  "))
    text = "".join(f'{escape(line)}<br align="left"/>' for line in lines)
    return [f'<tr><td bgcolor="{FOOTER_COLOR}" align="left"><font point-size="10">{text}</font></td></tr>']


def table_label(table: Table) -> str:
    """HTML-like label for one table: a header row, one <tr> per column, then any multi-column rules.

    Give each column's <td> a port="<column name>" so edges can attach to it.
    """
    # Style Params
    border = 0
    cellborder = 1
    cellspacing = 0

    rows = [f'<tr><td bgcolor="{HEADER_COLOR}"><b>{escape(table.name)}</b></td></tr>']
    rows.extend(column_rows(table))
    rows.extend(footer_rows(table))
    joined_rows = "\n".join(rows)

    # Table Creation
    label = f'<<table border="{border}" cellborder="{cellborder}" cellspacing="{cellspacing}">\n{joined_rows}\n</table>>'
    return label


def is_optional(table: Table | None, fk: ForeignKey) -> bool:
    """True if a row may have no parent: a foreign key column can be NULL. Primary key columns can't."""
    if table is None:
        return False
    columns = [table.column(name) for name in fk.from_columns]
    return any(c is not None and c.nullable and not table.is_primary_key(c.name) for c in columns)


def is_one_to_one(table: Table | None, fk: ForeignKey) -> bool:
    """True if at most one row can point at each parent: the foreign key columns are unique."""
    if table is None:
        return False
    from_columns = {name.lower() for name in fk.from_columns}
    unique_sets = [table.primary_key, *table.unique_sets]
    if any(from_columns == {name.lower() for name in names} for names in unique_sets):
        return True
    column = table.column(fk.from_columns[0])
    return len(fk.from_columns) == 1 and column is not None and column.unique


def composite_attributes(fk: ForeignKey, number: int) -> list[str]:
    """DOT attributes that mark the arrows of one composite foreign key as a group."""
    color = COMPOSITE_COLORS[(number - 1) % len(COMPOSITE_COLORS)]
    label = (fk.name or f"fk {number}").replace('"', '\\"')
    return [f'color="{color}"', f'fontcolor="{color}"', f'label="{label}"']


def endpoint(table_name: str, column_name: str | None, table: Table | None) -> str:
    """table:port, spelled the way the table declared them. Just the table if there's no such column.

    SQL ignores case but DOT doesn't, so REFERENCES USERS(ID) has to become
    users:id or Graphviz would draw a second box.
    """
    if table is None:
        return dot_id(table_name)
    column = table.column(column_name) if column_name is not None else None
    if column is None:
        return dot_id(table.name)
    return f"{dot_id(table.name)}:{dot_id(column.name)}"


def missing_table_nodes(schema: Schema) -> list[str]:
    """A dashed box for each table that foreign keys reference but the file doesn't define."""
    names = {fk.to_table: None for fk in schema.foreign_keys if schema.table(fk.to_table) is None}
    lines = []
    for name in names:
        label = name.replace('"', '\\"')
        lines.append(f'  {dot_id(name)} [label="{label}", shape=box, style=dashed];')
    return lines


def has_parent_on_right(schema: Schema, table: Table) -> bool:
    """True if this table has a foreign key to another table that Graphviz will place to its right.

    A parent normally goes right of its child. When two tables point at each
    other, Graphviz puts the one declared first on the left.
    """
    for fk in table.foreign_keys:
        target = schema.table(fk.to_table)
        if target is table:
            continue
        points_back = target is not None and any(schema.table(back.to_table) is table for back in target.foreign_keys)
        if not points_back or schema.tables.index(target) > schema.tables.index(table):
            return True
    return False


def loop_side(schema: Schema, table: Table) -> str:
    """The compass side for a self-reference, which leaves and returns on one side of the table.

    Graphviz doesn't leave room for these loops, and they grow with the table's
    width, so a loop goes on the left ("w") if a parent table is on the right.
    """
    return "w" if has_parent_on_right(schema, table) else "e"


def rank_separation(schema: Schema) -> float:
    """Inches between ranks of tables, with room for a self-reference loop that has tables on both sides.

    Such a loop reaches out almost as far as its table is wide, and there's no free side to put it on.
    """
    widest = 0
    for table in schema.tables:
        points_at_itself = any(schema.table(fk.to_table) is table for fk in table.foreign_keys)
        has_child = any(
            other is not table and schema.table(fk.to_table) is table
            for other in schema.tables for fk in other.foreign_keys
        )
        if points_at_itself and has_child and has_parent_on_right(schema, table):
            widest = max(widest, *(len(row) for row in row_texts(table)), 0)
    return max(RANK_SEPARATION, round(widest * CHAR_WIDTH, 1))


def foreign_key_edges(schema: Schema) -> list[str]:
    """One DOT edge per foreign key column pair.

    The edge defaults in to_dot() draw many-to-one, so a required
    foreign key needs no attributes of its own.
    """
    edges = []
    composite_number = 0

    for key in schema.foreign_keys:
        from_table = schema.table(key.from_table)
        to_table = schema.table(key.to_table)

        # Computed once per key, so every column pair of a composite key gets the same attributes.
        attributes = []
        if is_optional(from_table, key):
            attributes.append("style=dashed")
        if is_one_to_one(from_table, key):
            attributes.append("arrowtail=tee")
        if len(key.from_columns) > 1:
            composite_number += 1
            attributes.extend(composite_attributes(key, composite_number))
        suffix = f" [{', '.join(attributes)}]" if attributes else ""

        side = f":{loop_side(schema, from_table)}" if from_table is not None and from_table is to_table else ""

        # With no columns to point at, as when the parent has no primary key, point at the table itself.
        to_columns = key.to_columns or [None] * len(key.from_columns)

        for from_col, to_col in zip(key.from_columns, to_columns):
            tail = endpoint(key.from_table, from_col, from_table)
            head = endpoint(key.to_table, to_col, to_table)
            edges.append(f"  {tail}{side} -> {head}{side}{suffix};")

    return edges


def to_dot(schema: Schema, dpi: int | None = None) -> str:
    """Build the full DOT text: one node per table, one edge per foreign key column pair.

    Arrows use crow's foot notation: a crow's foot at the many end and a bar at
    the one end. Dashed means optional. Arrows of the same composite foreign key
    share a color and label.
    """
    settings = [
        f"  graph [rankdir=LR, nodesep=0.4, ranksep={rank_separation(schema)}];",
        f'  node [shape=plaintext, fontname="{FONT}", fontsize=12];',
        f'  edge [dir=both, arrowtail=crow, arrowhead=tee, fontname="{FONT}", fontsize=10];',
    ]
    if dpi is not None:
        settings.insert(0, f"  graph [dpi={dpi}];")
    joined_settings = "\n".join(settings)

    joined_labels = "\n".join(f"  {dot_id(table.name)} [label={table_label(table)}];" for table in schema.tables)
    joined_missing = "\n".join(missing_table_nodes(schema))
    joined_edges = "\n".join(foreign_key_edges(schema))

    return f"digraph schema {{\n{joined_settings}\n{joined_labels}\n{joined_missing}\n{joined_edges}\n}}"


def render(dot_text: str, output: Path) -> Path:
    """Render DOT text to a file and return its path. The extension picks the format (.svg, .png, .pdf).

    A path with no extension gets .svg. Raises ValueError for an unknown format.
    """
    if not output.suffix:
        output = output.with_suffix(".svg")
    fmt = output.suffix.lstrip(".").lower()

    # pipe() returns the bytes. Source.render() would write a temporary file at the output
    # path minus its extension, so -o schema.sql.svg would overwrite and delete schema.sql.
    data = graphviz.Source(dot_text).pipe(format=fmt)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output
