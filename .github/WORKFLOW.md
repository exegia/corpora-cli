# Branching and release

Two long-lived integration lanes (`dev`, `next`) plus `main` and the tags.
Release branches are temporary and versioned.

```
<type>/<slug> ──PR──> dev ──(daily/manual)──> next ──cut──> release/vX.Y.Z ──draft PR──> main
                 (deleted on merge)                                         (deleted on release)
```

Same model as [corpora-py](https://github.com/exegia/corpora-py). This repo is
a **Homebrew tap**, which changes what "release" means: the formula bump
`bump.yml` lands on `main` after each corpora-py tag IS the deploy — the tap's
committed state on `main` is what `brew install exegia/corpora-cli/corpora`
serves. The lanes version the tap **infrastructure** (formula changes, CI,
docs); the corpora version the formula ships lives in `Formula/corpora.rb` and
never rides the lanes.

Two version series therefore coexist:

- **`Formula/corpora.rb`** — the corpora-py version. Bumped by `bump.yml`
  committing directly to `main` as the automation App (on the `main` ruleset's
  bypass list). Fired by corpora-py's `publish.yml` via `repository_dispatch`,
  or manually.
- **`VERSION`** — the tap's own semver, playing the role corpora-py's root
  `pyproject.toml` version plays: written on `release/v*` by the cut,
  cross-checked against the branch name by the guard, read by `make
  tag-release` after the merge.

## Feature branches

Named `<type>/<slug>` — `feat`, `fix`, `chore`, `docs`, `ci`, `refactor`,
`test`, `perf`, `build`, `style`, `revert`. (Git forbids `:` in a ref name, so
the conventional-commit form lives in the **PR title**: `feat: add parser`.)

Branch off `dev` and open a PR back into it. While the PR is a draft only the
guard runs; marking it **ready for review** starts the check and the AI
review, which then re-run on every push. `guard` and `check` are required, so
a red one cannot land.

**Stacked PRs** (a feature branch based on another feature branch, not `dev`
directly) are supported: the guard validates a `<type>/<slug>` base the same
way it validates the head, so `feat/b → feat/a → dev` passes as long as both
branches and the title follow the convention. Merge bottom-up; each merge
rebases the remaining stack onto `dev`. The `review` job runs on any non-draft
PR whose base passed the guard (including stacked PRs).

When it merges the branch deletes itself (repository setting) and `dev` moves
forward. Nothing is versioned yet.

Dependabot is the one exception: it opens `dependabot/<ecosystem>/<dep>-<ver>`
with a `Bump X from A to B` title, and neither is renameable. `make pr-guard`
waves those through whichever branch they target.

## `dev` and `next`

`dev` is the working branch. Features land here all day.

`next` is staging. A scheduled workflow (22:00 UTC daily) and a manual
**Promote to next** action open a PR from `dev` into `next` when `dev` is
ahead. That PR auto-merges once `guard` and `check` pass. Every push to
`next` also runs the platform matrix (macOS versions + Linuxbrew).

## Versioning

The promote job classifies the bump from line-count churn
(`git diff --shortstat origin/next...origin/dev`, insertions + deletions):

| Churn | Makefile bump | Semver | Your label |
|-------|---------------|--------|------------|
| `< 100` | `patch` | `0.0.+1` | minor |
| `100–999` | `minor` | `0.+1.0` | major |
| `≥ 1000` | `major` | `+1.0.0` | breaking |

`workflow_dispatch` can override with `major` / `minor` / `patch`. The chosen
version is stored on the promote PR as `<!-- corpora-release: vX.Y.Z -->` so
the cut still knows it after `dev` and `next` are equal.

The version is written into the `VERSION` file at the repo root. Version
lives only on `release/v*` until `main` is merged back.

## Release branches

Named `release/vX.Y.Z`, and always carry that version in `VERSION`. The guard
rejects a PR into `main` where the file and the branch name disagree.

A push to `next` cuts (or refreshes) the branch from `next` plus a
`chore(release): open vX.Y.Z` commit. Exactly one is in flight at a time: if a
draft PR into `main` is already open, later promotions fast-forward that same
branch and **keep its version**.

Last-minute fixes can still PR `<type>/<slug>` directly into that in-flight
`release/v*` (same guard/check/review as `dev`). A push refreshes the draft
into `main`.

The draft PR into `main` accumulates the changelog of everything on the
branch. Marking it ready for review runs the guard plus the full macOS
`brew style/audit/install/test` — the installable formula is the artifact, so
there is no separate `package` job.

Its ruleset deliberately omits `creation` and `deletion` rules — `make
cut-release` has to create it and `make delete-branch` has to remove it after
the release. The automation App is on the bypass list so it can push a
refresh without opening a PR.

## `main`

No direct pushes except the automation App's formula bumps (`bump.yml`);
otherwise PRs only, from `release/vX.Y.Z`. Merging one creates the `vX.Y.Z`
tag and GitHub Release, deletes the release branch, then opens PRs that merge
`main` back into `next` and `dev` (picking up any formula bumps that landed in
the meantime) and deletes leftover remote feature / `release/v*` heads.

It does **not** cut the next release branch. That waits for the next promote.

Nothing hangs off the tag here — the formula on `main` is already the
published state. The tag versions the tap infra itself.

## Workflows

| File            | Trigger                              | Does                                                |
| --------------- | ------------------------------------ | --------------------------------------------------- |
| `pr.yml`        | PR opened / ready / pushed           | `guard`, `check`, `review`                          |
| `promote.yml`   | 22:00 UTC daily / manual             | bootstrap lanes, open `dev` → `next` PR, auto-merge |
| `next.yml`      | push to `next`                       | cut/refresh `release/v*`                            |
| `pr-merged.yml` | push to `release/v*`                 | upsert the draft release PR into `main`             |
| `release.yml`   | PR merged into `main`                | tag, sync lanes, cleanup                            |
| `matrix.yml`    | push to `next` / `release/v*`, weekly | macOS versions + Linuxbrew coverage                |
| `bump.yml`      | `repository_dispatch` / manual       | bump `Formula/corpora.rb` to a corpora-py release   |
| `automerge.yml` | Dependabot PR                        | enables auto-merge                                  |

Every step in the first five is a `make` target, so anything CI does can be
reproduced locally.

### Merge methods differ by level

Feature PRs into `dev` (or an in-flight `release/v*`) are **squashed** — that
is this repo's convention and it keeps each feature one commit. PRs into
`next` and the release PR into `main` are a **merge**, and the rulesets
enforce that. Squashing the release PR would collapse the whole release into
a single commit, and `gh release --generate-notes` would have nothing to list.

### The tag must not be created by `GITHUB_TOKEN`

`make tag-release` runs with the automation App's token. The `Publishing`
ruleset on `refs/tags/v*` refuses tag creation from anything not on its
bypass list, and if a tag-triggered workflow is ever added here, events
raised by `GITHUB_TOKEN` would not start it.

The same rule is why `pr-merged.yml`, `promote.yml`, `next.yml` and `bump.yml`
run as the App: a PR opened by `GITHUB_TOKEN` cannot trigger further
workflows, and `guard` and `check` are *required* checks — those PRs would
never be mergeable. `bump.yml` additionally needs the App because its commit
goes straight to protected `main`.

### Apply the rulesets after this lands on `main`

`.github/rulesets/*.json` is inert until `make rulesets-apply`. The
`Publishing` ruleset on `refs/tags/v*` carries `creation` and
`required_signatures` rules, so anything not on its bypass list is refused
when it tries to create `vX.Y.Z`. The checked-in files carry the automation
App (`corpora-ui-automation`, Integration `4425676`) as a bypass actor — on
`main` too, unlike corpora-py, because `bump.yml` pushes formula bumps
directly. Without that entry `make tag-release` cannot tag and the bump
cannot land.

```bash
make rulesets-diff     # what GitHub has now
make rulesets-apply    # push all five files
```

`make rulesets-apply` matches by `.name`, so a file must keep the name of the
ruleset already on GitHub (`Protect main branch`, `Protect dev branch`,
`Protect next branch`, `Protect release branches`, `Publishing`) or a second
one is created alongside it.

Enable **Allow auto-merge** and **Automatically delete head branches** on the
repository. Promote and post-release sync PRs use `gh pr merge --auto`.

## Bootstrap and manual operations

There are no `dev` / `next` branches until the first wrapup. Run the
**Release** workflow manually (`Actions → Release → Run workflow`) — the
release job skips and wrapup creates the lanes. Locally:

```bash
make bootstrap-lanes
```

`dev` is created from the newest `release/v*` if one exists, otherwise `main`.
`next` is created from `main`. Then run **Promote to next** (or wait until
22:00 UTC) once there is work on `dev`.

Other useful targets:

```bash
make ci                            # what CI runs on a PR (needs Homebrew)
make pkg-version                   # the version in the VERSION file
make churn-info FROM=origin/next TO=origin/dev
make next-version BUMP=patch       # what the next tag would be called
make release-notes RANGE=origin/main..HEAD
make cleanup-local                 # prune local feature / release branches
make rulesets-diff                 # rulesets GitHub actually has
make rulesets-apply                # push .github/rulesets/*.json
```

`make tag-release` is idempotent — a tag already released is skipped, not an
error.

Everything is parameterised on `TRUNK`, so a one-off against a different trunk
is `make pr-guard TRUNK=some-branch ...`.

Scheduled workflows are read from the **default branch**. `promote.yml` will
not fire on a cron until this file has shipped to `main`.

## Secrets

| Name                                               | Where            | Used by                     |
| -------------------------------------------------- | ---------------- | --------------------------- |
| `AUTOMATION_APP_ID` / `AUTOMATION_APP_PRIVATE_KEY` | **organisation** | opening PRs, branches, tags, formula bumps |
| `CLAUDE_CODE_OAUTH_TOKEN`                          | **organisation** | the AI review (optional)    |

All three are **organisation** secrets on `exegia`, inherited by this repo —
`gh api repos/exegia/corpora-cli/actions/secrets` returns an empty list and is
not evidence they are missing; use `gh api orgs/exegia/actions/secrets`. The
backing App is `corpora-ui-automation` (Integration `4425676`), installed
org-wide with `contents: write` + `pull_requests: write`.

Without `CLAUDE_CODE_OAUTH_TOKEN` the review job skips with a note in the job
summary rather than failing. The automation App is **not** optional:
`promote.yml`, `next.yml`, `pr-merged.yml`, `bump.yml` and the `wrapup` job
all fail at their first step without it. A PR opened with `GITHUB_TOKEN`
cannot trigger further workflows, so the release PR's own checks would never
start.
