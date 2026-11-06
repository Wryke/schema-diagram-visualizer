"""The data model: what the parser produces and the renderer consumes.

This file is the contract between the stages. It must not import anything
from the tokenizer, the parser, or Graphviz.

Phase 1:
  - Fill in the fields for each class below.
  - Then build a Schema by hand (see examples/hand_built.py) and render it.
"""

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    type: str  # e.g. "VARCHAR(255)", kept as text
    nullable: bool = True
    unique: bool = False
    default: str | None = None
    check: str | None = None


@dataclass
class ForeignKey:
    from_table: str
    from_columns: list[str]
    to_table: str
    to_columns: list[str]
    name: str | None = None
    on_delete: str | None = None


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)   # e.g. ["project_id", "employee_id"]
    checks: list[str] = field(default_factory=list)

    def column(self, name: str) -> Column | None:
        """Look up a column by name (case-insensitive), or return None."""
        # TODO: same pattern as Schema.table, but over self.columns
        raise NotImplementedError

    def is_primary_key(self, column_name: str) -> bool:
        """True if the column is part of this table's primary key (case-insensitive)."""
        # TODO: is column_name.lower() among the lowercased names in self.primary_key?
        raise NotImplementedError


@dataclass
class Schema:
    tables: list[Table] = field(default_factory=list)

    def table(self, name: str) -> Table | None:
        """Look up a table by name, or return None."""
        for t in self.tables:
            if t.name.lower() == name.lower():
                return t
        return None

    @property
    def foreign_keys(self) -> list[ForeignKey]:
        """Every foreign key in the schema, across all tables."""
        result = []
        for table in self.tables:
            result.extend(table.foreign_keys)
        return result
