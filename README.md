<p align="center">
  <img src="docs/logo.png" alt="corpora logo" width="140">
</p>

<h1 align="center">corpora</h1>

<p align="center">
  Convert EPUBs, PDFs, HTML, TEI/XML, and plain text into queryable
  <code>.corpus</code> archives — from your terminal.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/homebrew-exegia%2Fcorpora%2Fcli-yellow.svg" alt="Homebrew formula">
</p>

<p align="center">
  <img src="docs/corpora-convert.gif" alt="corpora converting an EPUB into a .corpus archive" width="800">
</p>

`corpora` is the terminal front end for the
[corpora-py](https://github.com/exegia/corpora-py) toolchain: it parses a
source document, builds a [Text-Fabric](https://annotation.github.io/text-fabric/)
dataset from it, and packages the result as a single portable `.corpus`
archive that the rest of the toolchain (API, MCP server, storage backends)
can query.

## Installation

Install with [Homebrew](https://brew.sh). The repo doesn't carry Homebrew's
`homebrew-` name prefix, so tap it by URL once, then install:

```bash
brew tap exegia/corpora https://github.com/exegia/corpora-cli
```

```bash
brew install exegia/corpora/cli
```

This builds the CLI into its own virtualenv (Python 3.13, resolved from PyPI)
and links three commands:

| Command | What it does |
| --- | --- |
| `corpora` | Conversion CLI + interactive terminal UI |
| `corpora-api` | Combined FastAPI app (conversion API at `/convert`, MCP server at `/mcp`) |
| `cf-mcp` | Standalone MCP server (stdio) for AI clients |

Verify the install:

```bash
corpora --help
```

<img src="docs/corpora-help.png" alt="corpora --help output" width="720">

Upgrade or remove later with:

```bash
brew upgrade exegia/corpora/cli
```

```bash
brew uninstall exegia/corpora/cli
```

## Usage

```text
usage: corpora [-h] {convert,validate,library} ...
```

Output is line-oriented and scripting-friendly: color drops away when piped,
and `NO_COLOR` is honoured.

### `corpora convert` — document → `.corpus`

```bash
corpora convert book.epub --name "My Book" -o book.corpus
corpora convert dataset.zip --format tf_zip
corpora convert notes.txt          # format inferred from the extension
```

| Argument / option | Description |
| --- | --- |
| `source` | Path to the source document. |
| `-f`, `--format` | Source format — see the table below. Inferred from the file extension when omitted; **required for `.zip` sources**. |
| `-n`, `--name` | Corpus name (fallback when the source has no title). |
| `-d`, `--description` | Corpus description. |
| `-c`, `--category` | Corpus structure category: `document`, `book`, or `religious`. Auto-detected when omitted; an upgrade the document tree can't support is downgraded with a warning. |
| `-o`, `--output` | Output `.corpus` path (default: `./<slugified-title>.corpus`). |
| `--force` | Overwrite the output file if it already exists. |

Supported formats:

| Format | Sources |
| --- | --- |
| `epub` | `.epub` e-books |
| `pdf` | `.pdf` documents |
| `html` | `.html` / `.htm` pages |
| `xml`, `tei` | XML and TEI-encoded texts |
| `plain` | `.txt` plain text |
| `tf_zip` | Zipped Text-Fabric datasets |
| `tei_zip` | Zipped TEI collections |

### `corpora validate` — integrity checks

```bash
corpora validate book.corpus
```

Runs the corpus integrity checks over a `.corpus` file and prints a verdict
plus archive stats:

<img src="docs/corpora-validate.png" alt="corpora validate output" width="720">

### `corpora ui` — interactive terminal UI

```bash
corpora ui   # or just: corpora
```

Running `corpora` with no arguments opens a full-screen terminal UI with
**Convert**, **Validate**, and **Library** tabs — the same pipeline as the
CLI, driven by forms instead of flags. Press `q` to quit, `^p` for the
command palette.

<img src="docs/corpora-ui.png" alt="corpora interactive terminal UI" width="720">

### `corpora library` — manage stored archives

Manages archives on the configured storage backend:

```bash
corpora library list                      # list stored archives
corpora library publish book.corpus       # upload a local archive
corpora library download book.corpus      # download (--dest DIR to choose where)
corpora library show book.corpus          # print manifest + section tree
corpora library show book.corpus --ref 1  # print the passages under a section
corpora library delete book.corpus -y     # delete (-y skips the confirmation)
```

### `corpora-api` — HTTP API + MCP over HTTP

```bash
corpora-api   # serves http://127.0.0.1:8000
```

Boots the combined FastAPI app: the conversion API at `/convert` and the MCP
server mounted at `/mcp`.

### `cf-mcp` — MCP server for AI clients

`cf-mcp` speaks MCP over stdio, for use in an AI client's MCP configuration —
e.g. for Claude Desktop / Claude Code:

```json
{
  "mcpServers": {
    "corpora": { "command": "cf-mcp" }
  }
}
```

## Releases

The Homebrew formula tracks this repo's release tags. On each release,
[`bump.yml`](.github/workflows/bump.yml) rewrites `Formula/cli.rb`'s
url/version/sha256 from the tag tarball and commits to `main` — the bump
commit *is* the release of the formula. Manual bumps: *Actions → Bump formula
→ Run workflow* with the version.

## Development

This repo is both the Homebrew tap and the home of the CLI package itself: a
uv-managed Python package under [`src/corpora_cli`](src/corpora_cli) that
depends on the [corpora-py](https://pypi.org/project/corpora-py/)
distribution from PyPI for the pipeline (parsers, Text-Fabric conversion,
storage backends) and renders it as a Rich-styled, scriptable CLI.

```bash
uv sync            # resolve corpora-py + rich into .venv
uv run corpora --help
make pytest        # ruff + pytest over the package
```

The package version is dynamic from the repo's [`VERSION`](VERSION) file, so
the release lanes below version it.

### Contributing / CI

Same branch model as corpora-py — see
[`.github/WORKFLOW.md`](.github/WORKFLOW.md): branches are `<type>/<slug>`
with PR titles `<type>: summary`, targeting `dev`; a daily promote moves work
through `next` and a versioned `release/vX.Y.Z` into `main`. (The lanes
version the tap infra; the corpora version the formula ships stays on
`main`'s bump commits.) Every CI step is a make target:

```bash
make ci        # brew style + audit + install + test + pytest (what the PR check runs)
make pr-guard  # BASE/HEAD/TITLE validation (what the guard job runs)
```

`guard` and `check` (macOS: a real `brew install` + `brew test` of the
formula) run on every PR via [`pr.yml`](.github/workflows/pr.yml).

## License

[MIT](LICENSE)
