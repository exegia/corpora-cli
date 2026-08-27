
<p align="center">
  <img src="docs/git-banner.png" alt="corpora logo">
</p>

# corpora/cli

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

Install with [Homebrew](https://brew.sh) — one command, no separate tap step:
Homebrew taps [`exegia/corpora`](https://github.com/exegia/homebrew-corpora)
on the way in.

```bash
brew install exegia/corpora/cli
```

This builds the CLI into its own virtualenv (Python 3.13, resolved from PyPI)
and links three commands:

| Command       | What it does                                                              |
| ------------- | ------------------------------------------------------------------------- |
| `corpora`     | Conversion, validation and library CLI                                    |
| `corpora-api` | Combined FastAPI app (conversion API at `/convert`, MCP server at `/mcp`) |
| `cf-mcp`      | Standalone MCP server (stdio) for AI clients                              |

Verify the install:

```bash
corpora --help
```

<img src="docs/corpora-help.svg" alt="corpora --help output" width="760">

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

| Argument / option     | Description                                                                                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source`              | Path to the source document.                                                                                                                                        |
| `-f`, `--format`      | Source format — see the table below. Inferred from the file extension when omitted; **required for `.zip` sources**.                                                |
| `-n`, `--name`        | Corpus name (fallback when the source has no title).                                                                                                                |
| `-d`, `--description` | Corpus description.                                                                                                                                                 |
| `-c`, `--category`    | Corpus structure category: `document`, `book`, or `religious`. Auto-detected when omitted; an upgrade the document tree can't support is downgraded with a warning. |
| `-o`, `--output`      | Output `.corpus` path (default: `./<slugified-title>.corpus`).                                                                                                      |
| `--force`             | Overwrite the output file if it already exists.                                                                                                                     |

Supported formats:

| Format       | Sources                     |
| ------------ | --------------------------- |
| `epub`       | `.epub` e-books             |
| `pdf`        | `.pdf` documents            |
| `html`       | `.html` / `.htm` pages      |
| `xml`, `tei` | XML and TEI-encoded texts   |
| `plain`      | `.txt` plain text           |
| `tf_zip`     | Zipped Text-Fabric datasets |
| `tei_zip`    | Zipped TEI collections      |

<img src="docs/corpora-convert-help.svg" alt="corpora convert --help output" width="760">

### `corpora validate` — integrity checks

```bash
corpora validate book.corpus
```

Runs the corpus integrity checks over a `.corpus` file and prints a verdict
plus archive stats:

<img src="docs/corpora-validate.svg" alt="corpora validate output" width="760">

### `corpora library` — manage stored archives

Manages archives on the configured storage backend:

```bash
corpora library list                      # list stored archives
corpora library show book.corpus          # print manifest + section tree
corpora library show book.corpus --ref 1  # print the passages under a section
```

`publish`, `download` and `delete` write to shared storage on a person's
behalf, so they are hidden and locked until the CLI can sign in — see
[#28](https://github.com/exegia/homebrew-corpora/issues/28).

<img src="docs/corpora-library-list.svg" alt="corpora library list output" width="760">

`show` prints the archive's manifest, its section tree, and — with `--ref` —
the passages under a section:

<img src="docs/corpora-library-show.svg" alt="corpora library show output" width="760">

### `corpora-api` — HTTP API + MCP over HTTP

```bash
corpora-api   # serves http://127.0.0.1:8000
```

Boots the combined FastAPI app: the conversion API at `/convert` and the MCP
server mounted at `/mcp`.

## Releases

The Homebrew formula tracks this repo's release tags. On each release,
[`bump.yml`](.github/workflows/bump.yml) rewrites `Formula/cli.rb`'s
url/version/sha256 from the tag tarball and commits to `main` — the bump
commit _is_ the release of the formula. Manual bumps: _Actions → Bump formula
→ Run workflow_ with the version.

corpora-py releases don't touch the formula: pip resolves the newest
compatible corpora-py from PyPI at install time.

## Thanks to

- **[Cody Kingham](https://github.com/Context-Fabric/context-fabric)** — for
  [Context Fabric](https://github.com/Context-Fabric/context-fabric), the engine
  that compiles and queries the datasets every `.corpus` archive is built from.
- **[Will McGugan](https://github.com/textualize/rich)** — for
  [Rich](https://github.com/textualize/rich), which every line this CLI prints
  goes through.

## License

[MIT](LICENSE)
