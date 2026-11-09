"""Phase 4: the command-line entry point.

    diagram examples/basic.sql                       writes out/basic.svg
    diagram examples/basic.sql --open                and opens it
    diagram examples/basic.sql -o shop.png --dpi 200

`pip install -e .` creates the diagram command. `python -m schemadiagram` does the same thing.

Exit codes: 0 on success, even with warnings; 1 on an error with the input or
rendering; 2 on bad arguments.
"""

import argparse
import sys
import webbrowser
from pathlib import Path

import graphviz

from schemadiagram import parser, render_dot
from schemadiagram.model import Schema
from schemadiagram.tokenizer import TokenizeError

# Where diagrams go by default: the project's out folder, whichever folder the command runs from.
OUT_FOLDER = Path(__file__).resolve().parent.parent / "out"


class CliError(Exception):
    """A problem to show the user as a one-line message, without a traceback."""


def positive_int(text: str) -> int:
    """An argparse type for whole numbers above zero."""
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be a whole number above 0, not {text!r}")
    return value


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="diagram", description="Draw a diagram from a SQL schema file.")
    ap.add_argument("input", type=Path, help="path to a .sql file")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="output file; the extension picks the format (default: <input name>.svg in the out folder)")
    ap.add_argument("--dpi", type=positive_int, default=None, help="resolution for PNG output")
    ap.add_argument("--open", action="store_true", help="open the diagram when it's done")
    return ap


def read_schema(path: Path) -> Schema:
    """Read and parse a SQL file."""
    try:
        data = path.read_bytes()
        # SQL Server Management Studio saves UTF-16. utf-8-sig also accepts the
        # byte order mark some Windows editors add to the start of a UTF-8 file.
        text = data.decode("utf-16" if data[:2] in {b"\xff\xfe", b"\xfe\xff"} else "utf-8-sig")
    except FileNotFoundError:
        raise CliError(f"File not found: {path}") from None
    except UnicodeDecodeError:
        raise CliError(f"{path} isn't UTF-8 text. Save it as UTF-8 and try again.") from None
    except OSError as e:
        raise CliError(f"Can't read {path}: {e.strerror}") from None

    try:
        schema = parser.parse(text)
    except (TokenizeError, parser.ParseError) as e:
        raise CliError(f"{path}: {e}") from None

    if not schema.tables:
        raise CliError(f"{path}: no CREATE TABLE statements found")
    return schema


def write_diagram(schema: Schema, output: Path, dpi: int | None) -> Path:
    """Render a schema to a file and return the path written."""
    try:
        return render_dot.render(render_dot.to_dot(schema, dpi), output)
    except graphviz.ExecutableNotFound:
        raise CliError(
            "Graphviz isn't installed or isn't on PATH. Install it with: winget install --id Graphviz.Graphviz -e"
        ) from None
    except graphviz.CalledProcessError:
        raise CliError("Graphviz couldn't draw this schema. Its own message, if any, is above.") from None
    except ValueError:
        raise CliError(f"Unknown output format {output.suffix!r}. Try .svg, .png, or .pdf.") from None
    except OSError as e:
        raise CliError(f"Can't write {output}: {e.strerror}") from None


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        schema = read_schema(args.input)
        output = args.output or OUT_FOLDER / f"{args.input.stem}.svg"
        written = write_diagram(schema, output, args.dpi)
    except CliError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    for warning in schema.warnings:
        print(f"warning: {warning}", file=sys.stderr)

    tables = plural(len(schema.tables), "table")
    foreign_keys = plural(len(schema.foreign_keys), "foreign key")
    print(f"Wrote {written} ({tables}, {foreign_keys})")

    if args.open and not webbrowser.open(written.resolve().as_uri()):
        print(f"warning: couldn't open {written}", file=sys.stderr)
    return 0
