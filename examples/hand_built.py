"""Phase 1: build a Schema by hand and render it, before any parsing exists.

This is examples/basic.sql written out by hand, so in Phase 3 it doubles as
the expected result: parse(basic.sql) should equal this schema.

Values are stored the way they're written in the SQL:
  - nullable is only False where NOT NULL is written (even for PK columns)
  - DEFAULT and CHECK are kept as text, string quotes included
  - inline PRIMARY KEY / REFERENCES become Table.primary_key / ForeignKey

Run from the project folder:
    python examples/hand_built.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemadiagram.model import Column, ForeignKey, Schema, Table
from schemadiagram.render_dot import render, to_dot

schema = Schema(tables=[
    Table(
        name="users",
        columns=[
            Column("id", "SERIAL"),
            Column("email", "VARCHAR(255)", nullable=False, unique=True),
            Column("created_at", "TIMESTAMP", default="CURRENT_TIMESTAMP"),
        ],
        primary_key=["id"],
    ),
    Table(
        name="employees",
        columns=[
            Column("id", "SERIAL"),
            Column("user_id", "INT", nullable=False),
            Column("manager_id", "INT"),
            Column("salary", "NUMERIC(10, 2)", check="salary > 0"),
        ],
        foreign_keys=[
            ForeignKey("employees", ["user_id"], "users", ["id"]),
            ForeignKey("employees", ["manager_id"], "employees", ["id"]),  # self-reference
        ],
        primary_key=["id"],
    ),
    Table(
        name="projects",
        columns=[
            Column("id", "SERIAL"),
            Column("name", "VARCHAR(100)", nullable=False),
        ],
        primary_key=["id"],
    ),
    Table(
        name="project_members",  # many-to-many join table
        columns=[
            Column("project_id", "INT", nullable=False),
            Column("employee_id", "INT", nullable=False),
            Column("role", "VARCHAR(50)", default="'member'"),
        ],
        foreign_keys=[
            ForeignKey("project_members", ["project_id"], "projects", ["id"],
                       name="fk_project", on_delete="CASCADE"),
            ForeignKey("project_members", ["employee_id"], "employees", ["id"]),
        ],
        primary_key=["project_id", "employee_id"],
    ),
])

if __name__ == "__main__":
    dot = to_dot(schema)
    print(dot)
    print("Wrote", render(dot, Path("out/hand_built.svg")))
