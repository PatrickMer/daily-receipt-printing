# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A daily receipt printer that generates personalized thermal receipts via an Epson TM-T20II printer connected over the network (192.168.0.200). Users configure a receipt as a list of widgets (weather, calendar, bike stations, etc.) and the system renders + prints it on demand.

## Commands

All commands use `make`. Run `make help` for a full list.

```bash
make run RECEIPT=receipts/patrick.json   # Print a receipt
make test                                # Run pytest
make lint                                # Check formatting, lint, types (black + ruff + mypy)
make format                              # Auto-fix formatting and lint issues
make build                               # Full gate: lint + test
make clean                               # Remove caches and build artifacts

# Update E2E snapshot baselines
uv run pytest --update-snapshots
```

## Architecture

Widget-based architecture. Core flow: load receipt config (JSON) -> run each widget's `render()` -> collect ESC/POS actions -> layout engine adds header/separators/cut -> printer driver dispatches to python-escpos.

- `src/core/` — framework: config loading, context, actions model, widget runner, layout engine, printer driver, engine orchestration, CLI entry point
- `src/widgets/` — independent widgets (weather, bicimad, calendar, fun_fact, hello) auto-discovered via `__init_subclass__` + `pkgutil`
- `receipts/` — JSON receipt configs defining which widgets to include
- `tests/` — pytest suite with unit tests per module + E2E snapshot test

**Key concepts:**
- **Widgets** return `list[ESCPOSAction]` — printer-agnostic typed dataclasses
- **Layout engine** wraps widget output with header/separators/cut
- **Printer driver** dispatches actions to python-escpos (Network or Dummy)
- **Widget autodiscovery** — drop a .py in `src/widgets/`, define `widget_type`, it's registered
- **Failure isolation** — one widget failing doesn't block the rest

## Config

- `config.yaml` — printer connection and logging settings
- `.env` — secrets (GOOGLE_CALENDAR_ICAL_URL)
- `receipts/*.json` — per-user receipt definitions

## Key Files

- `src/core/main.py` — CLI entry point
- `src/core/engine.py` — orchestration (`print_receipt()`)
- `src/widgets/widget.py` — Widget ABC
- `config.yaml` — system config
- `receipts/patrick.json` — example receipt
