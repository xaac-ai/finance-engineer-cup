PERIOD ?= 2026-10

.PHONY: run test clean

## Run the full review for PERIOD (default 2026-10). Outputs land in out/$(PERIOD)/.
run:
	uv run workbench run --period $(PERIOD)

## Run the code tests.
test:
	uv run pytest -q

## Remove generated outputs for PERIOD.
clean:
	rm -rf out/$(PERIOD)
