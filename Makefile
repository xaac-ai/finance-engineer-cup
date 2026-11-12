PERIOD ?= 2026-10

.PHONY: run test clean scenario draft-terms jev-check review-findings

## Run the full review for PERIOD (default 2026-10). Outputs land in out/$(PERIOD)/.
run:
	uv run workbench run --period $(PERIOD)

## Run the code tests.
test:
	uv run pytest -q

## Run one Scenario: October's inputs with one deliberate change, compared with the untouched run.
## `make scenario` lists them; `make scenario NAME=extra-usage` writes out/scenarios/extra-usage/.
scenario:
	uv run python -m workbench.scenarios $(NAME)

## Remove generated outputs for PERIOD.
clean:
	rm -rf out/$(PERIOD)

## Agent step: draft Amendment terms with Claude (needs ANTHROPIC_API_KEY, or replays the committed cache).
## Writes data/curated/$(PERIOD)/drafts/; never touches the curated terms.
draft-terms:
	uv run --group agents python -m workbench.agents.drafter --period $(PERIOD)

## Agent step: Jev checks each curated and drafted Amendment term against the Amendment text (needs
## TYPESAFE_API_KEY, or replays the committed cache). Rerun after changing amendment_terms.yaml.
jev-check:
	uv run python -m workbench.agents.jev --period $(PERIOD)

## Agent step: Independent Review. A second agent classifies every customer x stream from source files only
## (needs ANTHROPIC_API_KEY, or replays the committed cache). `make run` compares it with the Findings.
review-findings:
	uv run --group agents python -m workbench.agents.reviewer --period $(PERIOD)
