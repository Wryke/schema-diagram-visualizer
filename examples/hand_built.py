"""Phase 1: build a Schema by hand and render it, before any parsing exists.

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
            Column("email", "VARCHAR(255)"),
        ],
    ),
    Table(
        name="employees",
        columns=[
            Column("id", "SERIAL"),
            Column("user_id", "INT"),
            Column("manager_id", "INT"),
        ],
        foreign_keys=[
            ForeignKey("employees", ["user_id"], "users", ["id"]),
            ForeignKey("employees", ["manager_id"], "employees", ["id"]),  # self-reference
        ],
    ),
])

if __name__ == "__main__":
    dot = to_dot(schema)
    print(dot)
    print("Wrote", render(dot, Path("out/hand_built.svg")))
