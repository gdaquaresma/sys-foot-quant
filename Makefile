.PHONY: install test generate-data backtest run

install:
	uv sync --extra dev

test:
	uv run pytest -v

run:
	./scripts/start_app.sh

generate-data:
	uv run python scripts/generate_synthetic_data.py --config configs/backtest_stage1.yaml

backtest: generate-data
	uv run python scripts/run_backtest.py --config configs/backtest_stage1.yaml
