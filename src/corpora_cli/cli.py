"""``corpora`` — terminal CLI over the corpora-py conversion pipeline.

Runs the exact same pipeline as corpora-api's ``POST /convert`` — upload
gate → parse → Text-Fabric → ``.cfm`` → ``.corpus`` → validation gate —
but locally and synchronously, with no server, jobs, or transport
involved: everything goes through the transport-free seams of the
corpora-py distribution (`admin.services.*`), which this package depends
on from PyPI.

Output goes through Rich — accent-coloured help, a live task list while a
conversion runs, tables for stored archives and corpus content, emoji and
semantic colour for status (see `corpora_cli.ui`) — but stays
line-oriented and scriptable: plain argparse subcommands, no interactive
screens or TUI.

Usage::

    corpora convert mobydick.epub --name "Moby Dick" -o mobydick.corpus
    corpora convert dataset.zip --format tf_zip
    corpora validate mobydick.corpus
    corpora schema mobydick.epub -o mobydick.schema.json
    corpora reconcile mobydick.corpus --schema mobydick.schema.json --yes
    corpora library list
    corpora library show mobydick.corpus --ref "Moby Dick 1"

``schema`` and ``reconcile`` answer a different question than ``validate``:
not "is the archive internally sound?" but "does it faithfully represent the
document it was converted from?" (issue #41). ``schema`` normalises the
source document into a reference schema; ``reconcile`` aligns that schema
with the archive's Text-Fabric sections — bridging the two sides' level
names with an explicit or inferred ``--map`` — and reports what the
conversion lost.

`library publish`, `download` and `delete` write to shared storage on a
person's behalf; they are hidden and locked until the CLI can sign in (see
`AUTH_ISSUE`).

Exit codes: 0 success; 1 work that was attempted and failed — a failed
conversion, a corpus that fails its integrity checks, a storage error; 2 a
request that was wrong — an unreadable source, an unknown format, a refused
overwrite, unconfigured storage, a locked command, the pre-conversion upload
gate, argparse's own usage errors, and a bare `corpora`.

Scripting contract: the only stdout of ``convert`` is the result path
(``corpus=$(corpora convert ...)``); logs and decoration go to stderr.
``library list``/``show`` print their tables to stdout — they *are* the
command's output — and degrade to plain text when piped (Rich drops
colour on a non-tty; ``NO_COLOR`` is honoured).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from admin.parsers.schema import CorpusCategory, SourceFormat
from admin.services.conversion import (
    ConversionError,
    CorpusValidationError,
    run_conversion,
    validate_archive,
)
from admin.services.upload_validation import validate_upload

from corpora_cli import ui

# Extension → format for the unambiguous cases. `.zip` is deliberately
# absent: magic bytes and extensions can't tell a Text-Fabric dataset ZIP
# from a TEI-document ZIP, so ZIP sources must pass an explicit --format.
_EXTENSION_FORMATS: dict[str, SourceFormat] = {
    ".epub": SourceFormat.EPUB,
    ".html": SourceFormat.HTML,
    ".htm": SourceFormat.HTML,
    ".xhtml": SourceFormat.HTML,
    ".xml": SourceFormat.XML,
    ".tei": SourceFormat.TEI,
    ".pdf": SourceFormat.PDF,
    ".txt": SourceFormat.PLAIN,
    ".text": SourceFormat.PLAIN,
    ".md": SourceFormat.PLAIN,
    ".markdown": SourceFormat.PLAIN,
}


def _slugify(name: str) -> str:
    """Kebab-case a display name for the default output filename.

    Mirrors the server's result-filename slugging (`jobs._slugify`) without
    importing `jobs` — that module spins up the `JobManager` thread pool at
    import time, which a one-shot CLI has no use for.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _infer_format(source: Path, declared: str | None) -> SourceFormat:
    if declared:
        return SourceFormat(declared)
    suffix = source.suffix.lower()
    if suffix == ".zip":
        raise ui.fail(
            "a .zip source is ambiguous — pass --format tf_zip "
            "(a Text-Fabric dataset) or --format tei_zip (TEI documents)."
        )
    inferred = _EXTENSION_FORMATS.get(suffix)
    if inferred is None:
        known = ", ".join(sorted(_EXTENSION_FORMATS))
        raise ui.fail(
            f"cannot infer a source format from '{source.name}' — "
            f"pass --format (recognized extensions: {known}, .zip with an "
            "explicit --format)."
        )
    return inferred


def _print_validation(summary: dict) -> None:
    """Render a validation summary to stderr: verdict, stats, reasons."""
    if summary.get("valid"):
        ui.success("Validation: valid")
    else:
        ui.log(f"{ui.ERR} Validation: INVALID", style="error")
    stats = summary.get("stats") or {}
    if stats:
        ui.block(ui.key_value_table(stats, key_header="stat", value_header="value"), ui.err)
    for reason in summary.get("reasons") or []:
        ui.log(f"  {ui.ERR} reason: {reason}", style="error")


def _cmd_convert(args: argparse.Namespace) -> int:
    source = Path(args.source).expanduser()
    if not source.is_file():
        raise ui.fail(f"source file not found: {source}")
    source_format = _infer_format(source, args.format)

    # The same pre-conversion gate as POST /convert (issue #173): reject
    # obviously non-convertible bytes before spending minutes converting.
    report = validate_upload(source, source_format)
    for warning in report.warnings:
        ui.warn(warning)
    if not report.convertible:
        for reason in report.reasons:
            ui.error(reason)
        raise SystemExit(2)

    category = CorpusCategory(args.category) if args.category else None

    def output_path_for(display_name: str) -> Path:
        if args.output:
            path = Path(args.output).expanduser()
        else:
            stem = _slugify(display_name) or _slugify(source.stem) or "corpus"
            path = Path.cwd() / f"{stem}.corpus"
        if path.exists() and not args.force:
            raise ui.fail(f"{path} already exists — pass --force to overwrite.")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # A live task list on a terminal; piped/CI output stays plain lines.
    reporter = ui.ConversionReporter()
    # text-fabric/cfabric print progress chatter straight to stdout; it has
    # to go to stderr so the only stdout line is the result path (the
    # scripting contract: `corpus=$(corpora convert ...)`). The live
    # reporter redirects stdout itself — reprinting the chatter above its
    # task list — so only the plain path wires the redirect by hand.
    stdout_cm: contextlib.AbstractContextManager[Any] = (
        contextlib.nullcontext() if reporter.live else contextlib.redirect_stdout(sys.stderr)
    )

    result: Path | None = None
    with tempfile.TemporaryDirectory(prefix="corpora-cli-") as tmp:
        try:
            with reporter, stdout_cm:
                result = run_conversion(
                    source_path=source,
                    work_dir=Path(tmp) / "work",
                    source_format=source_format,
                    output_path_for=output_path_for,
                    name=args.name or "",
                    description=args.description or "",
                    category=category,
                    on_log=reporter.log,
                    on_display_name=reporter.title,
                    on_validation=_print_validation,
                )
        except CorpusValidationError as exc:
            # The archive was already written before the gate ran — keep it
            # (the user may want to inspect it) but fail the command.
            ui.error(str(exc))
            return 1
        except ConversionError as exc:
            ui.error(str(exc))
            return 1

    print(result)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    archive = Path(args.corpus).expanduser()
    if not archive.is_file():
        raise ui.fail(f"corpus file not found: {archive}")
    summary = validate_archive(archive)
    _print_validation(summary)
    return 0 if summary.get("valid") else 1


# ── schema / reconcile ───────────────────────────────────────────────────────
# Source-fidelity checks (issue #41): `schema` extracts a reference schema
# from the original document, `reconcile` aligns it with a converted
# archive's Text-Fabric sections. Both are stdlib-only
# (`corpora_cli.reconcile`) so they work on archives the heavy loaders
# cannot open.


def _cmd_schema(args: argparse.Namespace) -> int:
    from xml.etree import ElementTree

    from corpora_cli.reconcile import docschema

    document = Path(args.document).expanduser()
    if not document.is_file():
        raise ui.fail(f"document not found: {document}")
    output = (
        Path(args.output).expanduser()
        if args.output
        else (Path.cwd() / f"{document.stem}.schema.json")
    )
    if output.exists() and not args.force:
        raise ui.fail(f"{output} already exists — pass --force to overwrite.")

    levels = [name.strip() for name in (args.levels or "").split(",") if name.strip()]
    try:
        schema = docschema.extract(str(document), args.format, levels)
    except docschema.SchemaError as exc:
        raise ui.fail(str(exc)) from exc
    except (ElementTree.ParseError, zipfile.BadZipFile, OSError) as exc:
        ui.error(f"cannot read {document.name}: {exc}")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    title = schema.get("title") or "(untitled)"
    ui.success(f"Schema: {schema['source']} [{schema['format']}] — {title}")
    ui.note(f"  levels: {' > '.join(schema['levels'])}")
    for level, count in schema["unit_counts"].items():
        ui.note(f"  {level}: {count} unit(s)")
    ui.note(f"  total words: {schema['total_words']:,}")
    print(output)
    return 0


def _locate_tf_dir(corpus: Path, extract_root: Path) -> Path:
    """Find the directory holding ``otype.tf`` — inside `corpus` if it is a
    directory, else inside the archive extracted to `extract_root`."""
    if corpus.is_dir():
        root = corpus
    else:
        try:
            with zipfile.ZipFile(corpus) as archive:
                archive.extractall(extract_root)
        except zipfile.BadZipFile as exc:
            raise ui.fail(f"{corpus} is neither a .tf directory nor a readable archive.") from exc
        root = extract_root
    if (root / "otype.tf").is_file():
        return root
    hits = sorted(root.rglob("otype.tf"), key=lambda p: len(p.parts))
    if not hits:
        raise ui.fail(f"no otype.tf found under {corpus} — not a Text-Fabric corpus.")
    return hits[0].parent


def _cmd_reconcile(args: argparse.Namespace) -> int:
    from corpora_cli import reconcile

    corpus = Path(args.corpus).expanduser()
    if not corpus.exists():
        raise ui.fail(f"corpus not found: {corpus}")
    schema_path = Path(args.schema).expanduser()
    if not schema_path.is_file():
        raise ui.fail(
            f"schema file not found: {schema_path} — create it with `corpora schema <document>`."
        )

    def confirm(rows: list[dict], unmapped_ref: list[str], unmapped_cor: list[str]) -> bool:
        ui.info("Inferred level mapping:")
        table = ui.table("reference", "corpus", "evidence")
        for row in rows:
            table.add_row(row["ref"], row["corpus"], reconcile.format_evidence(row))
        ui.block(table, ui.err)
        for level in unmapped_ref:
            ui.warn(f"unmapped reference level: {level}")
        for stype in unmapped_cor:
            ui.warn(f"unmapped corpus section type: {stype}")
        if args.yes:
            ui.note("Proceeding (--yes).")
            return True
        if not sys.stdin.isatty():
            return False
        from rich.prompt import Confirm

        return Confirm.ask("Proceed with this mapping?", console=ui.err)

    with tempfile.TemporaryDirectory(prefix="corpora-reconcile-") as tmp:
        tf_dir = _locate_tf_dir(corpus, Path(tmp))
        options = reconcile.Options(
            corpus_dir=str(tf_dir),
            schema_path=str(schema_path),
            map_pairs=args.map or [],
            map_file=args.map_file or "",
            level=args.level or "",
            ref_level=args.ref_level or "",
            label_feature=args.label_feature or "",
            tolerance=args.tolerance,
            report_path=args.report or "",
            json_path=args.json_out or "",
            patch_dir=args.patch_dir or "",
        )
        try:
            result = reconcile.run(options, confirm)
        except reconcile.MappingError as exc:
            raise ui.fail(str(exc)) from exc

    if not args.quiet:
        print(result.report, end="")
    errors = sum(1 for f in result.findings if f["severity"] == "error")
    if errors:
        ui.log(f"{ui.ERR} Reconciliation: FAIL ({errors} error finding(s))", style="error")
    else:
        ui.success("Reconciliation: PASS")
    return result.exit_code


# ── library ──────────────────────────────────────────────────────────────────
# The `/storage` and `/storage/{filename}/…` surfaces of corpora-api as
# plain subcommands,
# calling the same in-process services. Storage imports are lazy: the
# scripting subcommands must not pay for the storage backends.


def _storage():
    from admin.services.storage import make_corpus_storage

    return make_corpus_storage()


def _run_library(args: argparse.Namespace) -> int:
    from admin.services.storage import StorageError, StorageNotConfiguredError

    try:
        return args.library_func(args)
    except StorageNotConfiguredError as exc:
        raise ui.fail(f"storage not configured: {exc}") from exc
    except StorageError as exc:
        ui.error(f"storage error: {exc}")
        return 1


def _cmd_library_list(_args: argparse.Namespace) -> int:
    corpora = list(_storage().list())
    if not corpora:
        ui.info("No stored corpora.")
        return 0
    table = ui.table("filename", "size", "repo", justify=("left", "right", "left"))
    for item in corpora:
        size = f"{item.size_bytes / (1024 * 1024):.1f} MB" if item.size_bytes else "?"
        table.add_row(item.filename, size, item.repo_id)
    ui.block(table)
    ui.note(f"{ui.LIBRARY} {len(corpora)} stored corpora.")
    return 0


def _cmd_library_publish(args: argparse.Namespace) -> int:
    path = Path(args.corpus).expanduser()
    if not path.is_file():
        raise ui.fail(f"local corpus not found: {path}")
    # `ui.spinner` also keeps the backend off stdout — only the URL below
    # belongs there.
    with ui.spinner(f"Publishing {path.name}…"):
        stored = _storage().upload(path)
    ui.success(f"Published: {stored.filename}", emoji=ui.PUBLISH)
    print(stored.url)
    return 0


def _cmd_library_download(args: argparse.Namespace) -> int:
    dest_dir = Path(args.dest).expanduser() if args.dest else Path.cwd()
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Backend chatter stays off stdout (see `ui.spinner`); the path below is
    # the command's only stdout line.
    with ui.spinner(f"Downloading {args.filename}…"):
        dest = _storage().download(args.filename, dest_dir)
    ui.success(f"Downloaded: {args.filename}", emoji=ui.DOWNLOAD)
    print(dest)
    return 0


def _cmd_library_delete(args: argparse.Namespace) -> int:
    if not args.yes:
        if not sys.stdin.isatty():
            raise ui.fail(
                f"refusing to delete {args.filename} without --yes (stdin is not a terminal)."
            )
        from rich.prompt import Confirm

        prompt = f"{ui.TRASH} Delete [accent]{args.filename}[/accent] from storage?"
        if not Confirm.ask(prompt, console=ui.err):
            ui.note("Aborted.")
            return 1
    _storage().delete(args.filename)
    ui.success(f"Deleted: {args.filename}", emoji=ui.TRASH)
    return 0


# Publishing, downloading and deleting act on shared storage on someone's
# behalf, so they wait for `corpora auth` (issue #28): hidden from help and
# refusing to run until the CLI knows who is asking. The implementations above
# are left wired to `library_func` — flipping `func` back to `_run_library` is
# what unlocks them.
AUTH_ISSUE = "https://github.com/exegia/homebrew-corpora/issues/28"


LOCKED_LIBRARY_COMMANDS = ("publish", "download", "delete")


def _locked(command: str) -> SystemExit:
    return ui.fail(
        f"`corpora library {command}` needs a signed-in corpora account, and "
        f"`corpora auth` does not exist yet — see {AUTH_ISSUE}. "
        "`corpora library list` and `corpora library show` work without one."
    )


def _cmd_library_show(args: argparse.Namespace) -> int:
    from admin.services.corpus_detail import get_content, get_index, get_manifest

    # corpus_detail (via text-fabric) chatters on stdout; `ui.spinner` keeps
    # stdout clean for the rendered output.
    with ui.spinner(f"Reading {args.filename}…"):
        manifest = get_manifest(args.filename)
        index = get_index(args.filename)
        content = get_content(args.filename, ref=args.ref) if args.ref else None

    scalars = {
        key: value
        for key, value in manifest.items()
        if isinstance(value, (str, int, float, bool)) and str(value)
    }
    ui.heading(f"{ui.TITLE} manifest")
    ui.out.print(ui.key_value_table(scalars, key_header="field", value_header="value"))

    # `sections` is `{"levels": [...], "items": [...]}` (see
    # corpus_detail._build_sections); each item carries `title`/`ref` and
    # one level of `children`.
    sections: dict[str, Any] = index.get("sections") or {}
    ui.heading(f"{ui.SECTIONS} sections")
    ui.out.print(ui.section_tree(sections.get("items") or []))

    if content is not None:
        passages = [
            passage.get("text") if isinstance(passage, dict) else str(passage)
            for passage in content.get("passages") or []
        ]
        ui.heading(f"{ui.PASSAGE} {args.ref}")
        ui.out.print(ui.passage_table([text for text in passages if text]))
        total = content.get("total")
        shown = len(content.get("passages") or [])
        if total and total > shown:
            ui.note(f"… {shown} of {total} passages shown")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = ui.Parser(
        prog="corpora",
        description="Convert documents to .corpus archives locally, using "
        "the same pipeline as the corpora-api /convert endpoint.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert = subparsers.add_parser(
        "convert", help="Convert a source document into a .corpus archive."
    )
    convert.add_argument("source", help="Path to the source document.")
    convert.add_argument(
        "--format",
        "-f",
        choices=[fmt.value for fmt in SourceFormat],
        help="Source format (inferred from the file extension when omitted; "
        "required for .zip sources).",
    )
    convert.add_argument(
        "--name", "-n", help="Corpus name (fallback when the source has no title)."
    )
    convert.add_argument("--description", "-d", help="Corpus description.")
    convert.add_argument(
        "--category",
        "-c",
        choices=[cat.value for cat in CorpusCategory],
        help="Corpus structure category (auto-detected when omitted; an "
        "upgrade the document tree can't support is downgraded with a "
        "warning).",
    )
    convert.add_argument(
        "--output",
        "-o",
        help="Output .corpus path (default: ./<slugified-title>.corpus).",
    )
    convert.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    convert.set_defaults(func=_cmd_convert)

    validate = subparsers.add_parser(
        "validate", help="Run the corpus integrity checks over a .corpus file."
    )
    validate.add_argument("corpus", help="Path to a .corpus archive.")
    validate.set_defaults(func=_cmd_validate)

    schema = subparsers.add_parser(
        "schema",
        help="Extract a reference schema (levels, units, word shingles) from "
        "a source document, for `corpora reconcile`.",
    )
    schema.add_argument("document", help="Source document (epub, tei/xml, markdown, txt).")
    schema.add_argument(
        "--format",
        "-f",
        default="auto",
        choices=("auto", "epub", "xml", "markdown"),
        help="Reference format (inferred from the extension when omitted).",
    )
    schema.add_argument(
        "--levels", help="Comma-separated level names, outermost first (overrides detection)."
    )
    schema.add_argument("--output", "-o", help="Schema JSON path (default: ./<stem>.schema.json).")
    schema.add_argument(
        "--force", action="store_true", help="Overwrite the output file if it already exists."
    )
    schema.set_defaults(func=_cmd_schema)

    reconcile = subparsers.add_parser(
        "reconcile",
        help="Compare a converted corpus against its source document's "
        "reference schema and report what the conversion lost.",
    )
    reconcile.add_argument(
        "corpus", help="A .corpus archive, a Text-Fabric .zip, or a directory of .tf files."
    )
    reconcile.add_argument(
        "--schema", required=True, help="Reference schema JSON from `corpora schema`."
    )
    reconcile.add_argument(
        "--map",
        action="append",
        metavar="REF=CORPUS",
        help="Alias one reference level to one corpus section type "
        "(e.g. --map h1=book --map h2=chapter); repeatable. All mapped "
        "levels are compared pairwise. Without it the mapping is inferred "
        "and must be confirmed.",
    )
    reconcile.add_argument(
        "--map-file",
        help="Persisted level mapping (JSON): read when it exists (unless "
        "--map is given), and the confirmed mapping is written back to it.",
    )
    reconcile.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Accept the inferred level mapping without prompting (for scripts and CI).",
    )
    reconcile.add_argument(
        "--level", help="Corpus section type to compare (single-level escape hatch)."
    )
    reconcile.add_argument(
        "--ref-level", help="Reference level to compare (single-level escape hatch)."
    )
    reconcile.add_argument(
        "--label-feature",
        help="Node feature holding the section label (default: the matching sectionFeature).",
    )
    reconcile.add_argument(
        "--tolerance",
        type=int,
        default=3,
        help="Slot offset tolerated before a boundary counts as drifted (default: 3).",
    )
    reconcile.add_argument("--report", help="Write the Markdown report to this path.")
    reconcile.add_argument(
        "--json", dest="json_out", help="Write the machine-readable result to this path."
    )
    reconcile.add_argument(
        "--patch-dir", help="Write append-only .tf patches for missing units to this directory."
    )
    reconcile.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress the report on stdout."
    )
    reconcile.set_defaults(func=_cmd_reconcile)

    library = subparsers.add_parser(
        "library", help="Manage stored archives on the configured backend."
    )
    library_sub = library.add_subparsers(dest="library_command", required=True)

    lib_list = library_sub.add_parser("list", help="List stored archives.")
    lib_list.set_defaults(func=_run_library, library_func=_cmd_library_list)

    # `publish`, `download` and `delete` are deliberately not registered: a
    # locked command must stay out of the help *and* out of argparse's
    # "invalid choice: … (choose from …)" list. `main` intercepts them by
    # name, so someone who knows they exist gets an explanation rather than a
    # typo error. Unlocking them (issue #28) means registering them again as
    # `publish <corpus>`, `download <filename> [--dest DIR]` and
    # `delete <filename> [-y]`, each `set_defaults(func=_run_library,
    # library_func=_cmd_library_*)`.

    lib_show = library_sub.add_parser(
        "show", help="Show a stored archive's manifest and section tree."
    )
    lib_show.add_argument("filename", help="Stored archive filename.")
    lib_show.add_argument("--ref", help="Section reference whose passages should be printed.")
    lib_show.set_defaults(func=_run_library, library_func=_cmd_library_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    # An unexpected exception is a bug report: render it with frames and
    # source rather than a bare Python traceback (`corpora_cli.ui`).
    ui.install_traceback()
    resolved = list(sys.argv[1:] if argv is None else argv)
    # Intercepted before argparse ever sees them (see `build_parser`).
    if resolved[:1] == ["library"] and resolved[1:2] and resolved[1] in LOCKED_LIBRARY_COMMANDS:
        raise _locked(resolved[1])
    # Bare `corpora` prints the overview instead of argparse's terse usage
    # error.
    if not resolved:
        build_parser().print_help(sys.stderr)
        return 2
    args = build_parser().parse_args(resolved)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        # Ctrl-C is an answer, not a crash — no traceback for it.
        ui.log(f"{ui.WARN} interrupted.", style="warning")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
