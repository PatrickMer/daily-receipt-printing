# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A daily receipt printer that generates personalized thermal receipts via an Epson TM-T20II printer connected over the network (192.168.0.200). Users configure a receipt as a list of widgets (weather, calendar, bike stations, etc.) and the system renders + prints it on demand.

## Commands

```bash
# Run the main script
python3 src/core/main.py

# Run tests
python3 -m pytest tests/

# Run a single test file
python3 -m pytest tests/core/main_test.py
```

## Architecture

The project uses a widget-based architecture where receipts are composed of independent widgets.

**Core flow:** Load user receipt config (JSON) → execute each widget's `render(config, context)` → collect ESC/POS actions → send to printer.

**Key concepts:**
- **Widgets** return a list of `ESCPOSAction` objects (text, barcode, cut, etc.) that map directly to `python-escpos` method calls. Widgets are printer-agnostic.
- **Receipt configs** (JSON) define which widgets to include and their parameters. Each user has one receipt config.
- **Global context** (date, time, username) is injected into every widget at execution time.
- Widget failures are isolated — one failing widget doesn't block the rest of the receipt.

**Printer library:** [python-escpos](https://github.com/python-escpos/python-escpos) with the `TM-T20II` profile. Connected via `escpos.printer.Network`.

## Planned Structure (from notes.md)

```
src/
  core/           - main.py, generate_printable_receipt, connect_printer, load_configs
  widgets/        - widget.py (base class), weather.py, bicimad.py, calendar.py, fun-fact.py
receipts/         - user configs (e.g. patrick.json)
schemas/          - JSON Schema for receipt and widget params
tests/
```
