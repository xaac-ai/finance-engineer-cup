PERIOD ?= 2026-10

.PHONY: run test clean draft-terms

## Run the full review for PERIOD (default 2026-10). Outputs land in out/$(PERIOD)/.
run:
	uv run workbench run --period $(PERIOD)

## Run the code tests.
test:
	uv run pytest -q

## Remove generated outputs for PERIOD.
clean:
	rm -rf out/$(PERIOD)

## Agent step: draft Amendment terms with Claude (needs ANTHROPIC_API_KEY, or replays the committed cache).
## Writes data/curated/$(PERIOD)/drafts/; never touches the curated terms.
draft-terms:
	uv run --group agents python -m workbench.agents.drafter --period $(PERIOD)
