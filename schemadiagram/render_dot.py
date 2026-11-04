"""Phase 1 and 5: turn a Schema into Graphviz DOT text, and render it.

This file knows about Graphviz but nothing about SQL text or tokens.
"""

from pathlib import Path

import graphviz

from schemadiagram.model import ForeignKey, Schema, Table

# Colors for composite foreign keys; cycles if there are more than four.
COMPOSITE_COLORS = ["darkgreen", "purple", "darkorange", "navy"]


def escape(text: str) -> str:
    """Escape text for use inside an HTML-like label (& < > ")."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")


def table_label(table: Table) -> str:
    """HTML-like label for one table: a header row, then one <tr> per column.

    Give each column's <td> a port="<column name>" so edges can attach to it.
    """
    # Style Params
    border = 0
    cellborder = 1
    cellspacing = 0
    bgcolor = "lightblue"
    
    rows = []
    
    # Header Creation
    rows.append(f'<tr><td bgcolor="{bgcolor}"><b>{escape(table.name)}</b></td></tr>')
    
    # Column Building
    for column in table.columns:
        rows.append(f'<tr><td port="{escape(column.name)}" align="left">{escape(column.name)}  {escape(column.type)}</td></tr>')
        
    joined_rows = "\n".join(rows)
    
    # Table Creation
    label = f'<<table border="{border}" cellborder="{cellborder}" cellspacing="{cellspacing}">\n{joined_rows}\n</table>>'
    return label


def edge_attributes(fk: ForeignKey, number: int) -> str:
    """DOT attributes that mark the arrows of one composite foreign key as a group."""
    color = COMPOSITE_COLORS[(number - 1) % len(COMPOSITE_COLORS)]
    label = (fk.name or f"fk {number}").replace('"', '\\"')
    return f' [color="{color}", fontcolor="{color}", label="{label}"]'


def to_dot(schema: Schema, dpi: int | None = None) -> str:
    """Build the full DOT text: one node per table, one edge per foreign key column pair.

    Arrows of the same composite foreign key share a color and label.
    """
        
    settings =  (f'  graph [dpi={dpi}];\n' if dpi is not None else "") + '  node [shape=plaintext];\n'
    
    labels=[]
    
    for table in schema.tables:
        labels.append(f'{table.name} [label={table_label(table)}];')
    
    joined_labels = "\n".join(labels)
    
    edges = []
    composite_number = 0

    for key in schema.foreign_keys:
        # Computed once per key, so every column pair of a composite key gets the same attributes.
        attributes = ""
        if len(key.from_columns) > 1:
            composite_number += 1
            attributes = edge_attributes(key, composite_number)

        for from_col, to_col in zip(key.from_columns, key.to_columns):
            edges.append(f"  {key.from_table}:{from_col} -> {key.to_table}:{to_col}{attributes};")

    joined_edges = "\n".join(edges)
    
    dot = f'digraph schema {{\n{settings}{joined_labels}\n{joined_edges}\n}}'
    
    return dot


def render(dot_text: str, output: Path) -> Path:
    """Render DOT text to a file. The format comes from the extension (.svg, .png, .pdf)."""
    fmt = output.suffix.lstrip(".") or "svg"
    # render() appends the extension itself, so pass the path without it.
    result = graphviz.Source(dot_text).render(output.with_suffix(""), format=fmt, cleanup=True)
    return Path(result)
