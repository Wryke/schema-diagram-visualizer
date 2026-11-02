"""Phase 4: the command-line entry point.

    python -m schemadiagram examples/basic.sql -o out/basic.svg
"""

import argparse
from pathlib import Path


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="schemadiagram", description="Draw a diagram from a SQL schema file.")
    ap.add_argument("input", type=Path, help="path to a .sql file")
    ap.add_argument("-o", "--output", type=Path, default=Path("out/schema.svg"),
                    help="output file; the extension picks the format (default: out/schema.svg)")
    ap.add_argument("--dpi", type=int, default=None, help="resolution for PNG output")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # TODO (Phase 4):
    #   1. read args.input (friendly error if it doesn't exist)
    #   2. schema = parser.parse(text)  (catch TokenizeError / ParseError and print them)
    #   3. dot = render_dot.to_dot(schema, args.dpi)
    #   4. render_dot.render(dot, args.output)
    #      (catch graphviz.ExecutableNotFound: "Graphviz isn't installed or not on PATH")
    print(f"TODO: would render {args.input} to {args.output}")
    return 0
