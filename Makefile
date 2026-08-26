# Every CI step is a make target, mirroring exegia/corpora-py: the pipeline
# stays reproducible locally (`make ci` on a machine with Homebrew does what
# the check job does).

TAP      := exegia/corpora-cli
FORMULA  := $(TAP)/corpora
TYPES    := feat|fix|chore|docs|ci|refactor|test|perf|build|style|revert

.DEFAULT_GOAL := help

.PHONY: help tap style audit install test ci pr-guard

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

# Symlinked, not `brew tap <url>`: tapping clones the repo's committed state,
# which would silently audit/install something other than this checkout.
TAP_DIR := $(shell brew --repository)/Library/Taps/exegia/homebrew-corpora-cli

tap: ## Register this checkout as the exegia/corpora-cli tap (symlink)
	@mkdir -p "$(dir $(TAP_DIR))"; \
	[ -e "$(TAP_DIR)" ] || ln -s "$(CURDIR)" "$(TAP_DIR)"

style: tap ## Homebrew style check
	brew style $(TAP)

audit: tap ## Homebrew formula audit
	brew audit --strict --formula $(FORMULA)

install: tap ## Build/install the formula from this checkout
	brew install --formula $(FORMULA)

test: ## Run the formula's test block (convert -> validate round-trip)
	brew test $(FORMULA)

ci: style audit install test ## Everything the PR check job runs

pr-guard: ## Validate a PR's base, branch name and title (env: BASE, HEAD, TITLE).
	@set -eu; \
	: "$${BASE:?BASE is required}" "$${HEAD:?HEAD is required}"; \
	case "$$HEAD" in \
	dependabot/*) \
	  echo "guard skipped for dependabot: $$HEAD -> $$BASE"; exit 0;; \
	esac; \
	case "$$BASE" in \
	main) \
	  echo "$$HEAD" | grep -Eq '^($(TYPES))/[a-z0-9][a-z0-9._-]*$$' \
	    || { echo "::error::branch must be <type>/<slug> — one of $(TYPES) (got '$$HEAD')"; exit 1; }; \
	  printf '%s' "$${TITLE-}" | grep -Eq '^($(TYPES))(\([a-z0-9._/-]+\))?!?: .+' \
	    || { echo "::error::PR title must read '<type>: summary' (got '$${TITLE-}')"; exit 1; }; \
	  ;; \
	*/*) \
	  echo "$$BASE" | grep -Eq '^($(TYPES))/[a-z0-9][a-z0-9._-]*$$' \
	    || { echo "::error::stack base must be <type>/<slug> — one of $(TYPES) (got '$$BASE')"; exit 1; }; \
	  echo "$$HEAD" | grep -Eq '^($(TYPES))/[a-z0-9][a-z0-9._-]*$$' \
	    || { echo "::error::branch must be <type>/<slug> — one of $(TYPES) (got '$$HEAD')"; exit 1; }; \
	  printf '%s' "$${TITLE-}" | grep -Eq '^($(TYPES))(\([a-z0-9._/-]+\))?!?: .+' \
	    || { echo "::error::PR title must read '<type>: summary' (got '$${TITLE-}')"; exit 1; }; \
	  ;; \
	*) \
	  echo "::error::unexpected PR base '$$BASE' (PRs land on main)"; exit 1;; \
	esac; \
	echo "guard ok: $$HEAD -> $$BASE"
