"""The data model: what the parser produces and the renderer consumes.

This file is the contract between the stages. It must not import anything
from the tokenizer, the parser, or Graphviz.

Phase 1 TODO:
  - Fill in the fields for each class below.
  - Then build a Schema by hand (see examples/hand_built.py) and render it.
"""

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    type: str  # e.g. "VARCHAR(255)", kept as text
    # TODO: nullable, primary_key, unique, default, check


@dataclass
class ForeignKey:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    # TODO: on_delete? constraint name?


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    # TODO: table-level checks, composite primary key


@dataclass
class Schema:
    tables: list[Table] = field(default_factory=list)

    def table(self, name: str) -> Table | None:
        """Look up a table by name, or return None."""
        # TODO: should this be case-insensitive? SQL usually is.
        raise NotImplementedError
