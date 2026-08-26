# exegia/corpora-cli

Homebrew tap for the [corpora-py](https://github.com/exegia/corpora-py)
toolchain.

## Install

The repo doesn't carry Homebrew's `homebrew-` name prefix, so tap it by URL
once, then install:

```bash
brew tap exegia/corpora-cli https://github.com/exegia/corpora-cli
brew install corpora
```

This installs corpora-py into its own virtualenv and links three commands:

- **`corpora`** — terminal conversion CLI:

  ```bash
  corpora convert book.epub --name "My Book" -o book.corpus
  corpora convert dataset.zip --format tf_zip
  corpora validate book.corpus
  ```

- **`corpora-api`** — the combined FastAPI app (MCP server at `/mcp` +
  conversion API at `/convert`).
- **`cf-mcp`** — the standalone MCP server for AI clients.

## Releases

The formula tracks corpora-py's release tags. On each tagged PyPI publish,
corpora-py's `publish.yml` fires this repo's
[`bump.yml`](.github/workflows/bump.yml) (`bump-formula` dispatch), which
rewrites `Formula/corpora.rb`'s url/version/sha256 from the tag tarball and
commits to `main` — the bump commit *is* the release; there are no separate
lanes here. Manual bumps: *Actions → Bump formula → Run workflow* with the
version.

## Contributing / CI

Same conventions as corpora-py, adapted to a formula-only repo: branches are
`<type>/<slug>` and PR titles `<type>: summary`, targeting `main` directly.
Every CI step is a make target:

```bash
make ci        # brew style + audit + install + test (what the PR check runs)
make pr-guard  # BASE/HEAD/TITLE validation (what the guard job runs)
```

`guard` and `check` (macOS: a real `brew install` + `brew test` of the
formula) run on every PR via [`pr.yml`](.github/workflows/pr.yml).
