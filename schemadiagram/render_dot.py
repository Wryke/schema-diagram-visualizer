"""Phase 1 and 5: turn a Schema into Graphviz DOT text, and render it.

This file knows about Graphviz but nothing about SQL text or tokens.
"""

from pathlib import Path

import graphviz

from schemadiagram.model import Schema, Table


def escape(text: str) -> str:
    """Escape text for use inside an HTML-like label (& < > ")."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")


def table_label(table: Table) -> str:
    """HTML-like label for one table: a header row, then one <tr> per column.

    Give each column's <td> a port="<column name>" so edges can attach to it.
    """
    raise NotImplementedError


def to_dot(schema: Schema, dpi: int | None = None) -> str:
    """Build the full DOT text.

    TODO:
      - 'digraph schema {', graph/node defaults (node [shape=plaintext])
      - if dpi is given, add graph [dpi=...] (sharper PNGs)
      - one node per table using table_label()
      - one edge per foreign key: from_table:from_col -> to_table:to_col
      - self-references are just edges where both ends are the same table
    """
    raise NotImplementedError


def render(dot_text: str, output: Path) -> Path:
    """Render DOT text to a file. The format comes from the extension (.svg, .png, .pdf)."""
    fmt = output.suffix.lstrip(".") or "svg"
    # render() appends the extension itself, so pass the path without it.
    result = graphviz.Source(dot_text).render(output.with_suffix(""), format=fmt, cleanup=True)
    return Path(result)
