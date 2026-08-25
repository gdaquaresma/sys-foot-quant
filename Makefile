.PHONY: install test generate-data backtest

install:
	uv sync --extra dev

test:
	uv run pytest -v

generate-data:
	uv run python scripts/generate_synthetic_data.py --config configs/backtest_stage1.yaml

backtest: generate-data
	uv run python scripts/run_backtest.py --config configs/backtest_stage1.yaml
