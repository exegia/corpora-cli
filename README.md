# exegia/homebrew-tap

Homebrew formulae for [exegia](https://github.com/exegia) tools.

## Install

```bash
brew install exegia/tap/corpora
```

This installs the [corpora-py](https://github.com/exegia/corpora-py) toolchain
into its own virtualenv and links three commands:

- **`corpora`** — terminal conversion CLI:

  ```bash
  corpora convert book.epub --name "My Book" -o book.corpus
  corpora convert dataset.zip --format tf_zip
  corpora validate book.corpus
  ```

- **`corpora-api`** — the combined FastAPI app (MCP server at `/mcp` +
  conversion API at `/convert`).
- **`cf-mcp`** — the standalone MCP server for AI clients.

## Updating

The formula is bumped automatically on each corpora-py release tag by
[`bump.yml`](.github/workflows/bump.yml) (fired from corpora-py's publish
pipeline, or manually via *Actions → Bump formula → Run workflow* with the
new version).
