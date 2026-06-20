# Design Document

## Overview

A daily receipt printing system that generates personalized thermal receipts composed of independent, configurable widgets. Receipts are defined as JSON configurations and printed on-demand or via cron to a network-connected ESC/POS printer.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────┐
│ Trigger     │────▶│ Core Engine  │────▶│ Widget Runner  │────▶│ Printer │
│ (cron/CLI)  │     │ (main.py)    │     │ (render loop)  │     │ Driver  │
└─────────────┘     └──────────────┘     └────────────────┘     └─────────┘
                           │                      │
                    ┌──────┴──────┐        ┌──────┴──────┐
                    │ Config      │        │ Widgets     │
                    │ Loader      │        │ (autodiscov)│
                    └─────────────┘        └─────────────┘
```

### Core Flow

1. Trigger fires (cron or CLI invocation)
2. Core engine loads system config (`config.yaml`) and receipt config (`receipts/*.json`)
3. Widget runner iterates the receipt's widget list, injecting shared context (date, time)
4. Each widget fetches its data and returns a `list[ESCPOSAction]`
5. Core assembles the full action list (with layout: headers, separators, cuts)
6. Printer driver maps actions to `python-escpos` method calls and sends to the printer

### Configuration Split

| File | Purpose | Version controlled |
|------|---------|-------------------|
| `config.yaml` | System settings: printer IP, printer profile, log level, log file path | Yes |
| `.env` | Secrets (API keys) | No (gitignored) |
| `.env.example` | Template listing all required secrets with placeholders | Yes |
| `receipts/*.json` | Receipt definitions: layout options + ordered widget list with params | Yes |

### Widget Contract

Widgets are autodiscovered using `__init_subclass__` + `pkgutil.iter_modules`. Each widget file in `src/widgets/` defines a class inheriting from `Widget` with an explicit `widget_type` class variable that maps to the `"type"` field in receipt JSON configs.

```python
from abc import ABC, abstractmethod

class Widget(ABC):
    widget_type: str  # Maps to receipt JSON "type" field (e.g. "weather")
    required_secrets: list[str] = []

    _registry: dict[str, type["Widget"]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return
        widget_type = getattr(cls, "widget_type", None)
        if widget_type is None:
            raise TypeError(f"{cls.__name__} must define 'widget_type'")
        if widget_type in Widget._registry:
            raise ValueError(f"Duplicate widget_type '{widget_type}'")
        Widget._registry[widget_type] = cls

    @abstractmethod
    def render(self, params: dict, context: Context) -> list[ESCPOSAction]:
        ...

    @classmethod
    def get(cls, widget_type: str) -> type["Widget"]:
        """Look up widget class by type string."""
        ...
```

Discovery at startup (`src/widgets/__init__.py`):
```python
def discover_widgets() -> None:
    """Import all modules in widgets/ to trigger __init_subclass__ registration."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__package__}.{module_info.name}")
        except Exception:
            logger.exception(f"Failed to load widget module '{module_info.name}'")
```

- **Secrets declaration**: Each widget declares `required_secrets` as a class variable. At startup, the system validates all secrets are present in the environment and fails loudly if not.
- **Failure isolation**: A widget that raises an exception is logged and skipped; other widgets still render.
- **Printer-agnostic output**: Widgets return `ESCPOSAction` objects, never interact with the printer directly.

### ESCPOSAction Schema

Actions map to `python-escpos` methods. The valid action set is derived at runtime from the configured printer profile using `printer.profile.supports(feature)` and `printer.profile.get_columns(font)`.

Supported action types (availability depends on printer profile):

| Action | Maps to | Key params |
|--------|---------|------------|
| `set` | `printer.set(...)` | `align`, `bold`, `underline`, `width`, `height`, `font`, `invert` |
| `text` | `printer.text(txt)` | `content` |
| `feed` | `printer.print_and_feed(n)` | `lines` |
| `image` | `printer.image(path, ...)` | `path`, `center`, `impl` |
| `qr` | `printer.qr(content, ...)` | `content`, `size`, `native`, `center` |
| `barcode` | `printer.barcode(code, bc, ...)` | `code`, `bc_type`, `height`, `width`, `pos` |
| `cut` | `printer.cut(mode)` | `mode` ("FULL" or "PART") |

Profile feature flags used for capability detection:
- `paperFullCut`, `paperPartCut` → cut actions
- `barcodeA`, `barcodeB` → barcode support (B is superset of A)
- `qrCode` → native QR code
- `bitImageRaster`, `graphics`, `bitImageColumn` → image modes

The `set()` method is **stateful and sticky** — formatting persists until explicitly changed. The driver must call `set_with_default()` between widgets to reset state.

### Printer Driver

Uses `escpos.printer.Network`:

```python
Network(host: str, port: int = 9100, timeout: int = 60, profile: str = "TM-T20II")
```

Key behaviors:
- **Lazy connection**: Socket opens on first method call, not on construction. Call `open()` explicitly for fast-fail.
- **No auto-reconnect**: If connection drops, must catch exception and re-create.
- **Timeout**: Default 60s. Use 10s for quick failure detection.
- **Always close**: Use try/finally — `__del__` is unreliable.

For testing, use `escpos.printer.Dummy` — captures raw bytes without a real printer. This enables the E2E snapshot testing approach.

### Receipt Config Structure

```json
{
  "receipt": {
    "name": "patrick",
    "layout": {
      "header": true,
      "separator": "dashes",
      "cut_at_end": true,
      "feed_before_cut": 3
    },
    "widgets": [
      {
        "type": "weather",
        "params": {
          "location": "madrid",
          "fields": ["temperature", "precipitation"],
          "period": "hourly"
        }
      }
    ]
  }
}
```

### Logging

- All output (info, error, debug) is written to both stdout and a log file.
- Log file location and rotation configured in `config.yaml`.
- Each execution is timestamped for debugging past runs.
- Log level is configurable (default: INFO).

### Trigger Interface

The system exposes a single entry point: "print this receipt". Both cron and a future physical button (or HTTP endpoint) invoke the same function:

```python
def print_receipt(receipt_path: str) -> None:
    ...
```

Cron calls this directly. Other triggers can wrap it without changing core logic.

### Project Tooling

| Concern | Tool | Config Location |
|---------|------|-----------------|
| Dependency management | `uv` | `pyproject.toml` + `uv.lock` |
| Formatting | Black (line-length 88) | `[tool.black]` in pyproject.toml |
| Linting + imports | Ruff (E, W, F, I, N, UP, B, SIM, PTH, RUF) | `[tool.ruff]` in pyproject.toml |
| Testing + coverage | pytest + pytest-cov (80% min) | `[tool.pytest.ini_options]` |
| Type checking | mypy (strict mode) | `[tool.mypy]` in pyproject.toml |
| Task runner | Makefile | `Makefile` |

Makefile targets: `format`, `lint`, `test`, `build` (lint + test), `run`, `clean`.

All tools run via `uv run` to use the project's virtual environment without manual activation.

---

## Technical Decisions (from research)

### Weather: Open-Meteo API

- **No API key required**, no signup, no credit card
- 10,000 requests/day free (non-commercial)
- Hourly forecast with ECMWF data (gold standard for Europe)
- Endpoint: `https://api.open-meteo.com/v1/forecast?latitude=40.4168&longitude=-3.7038&hourly=temperature_2m,precipitation,precipitation_probability,weathercode&timezone=Europe/Madrid&forecast_days=1`
- Geocoding: `https://geocoding-api.open-meteo.com/v1/search?name=Madrid`
- Response: flat JSON arrays indexed by hour

### BiciMad: GBFS v3.0 Feed (primary) + CityBikes API (fallback)

**Primary — GBFS v3.0 (no auth, official):**
- Discovery: `https://madrid.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json`
- Station info: `https://madrid.publicbikesystem.net/customer/gbfs/v3.0/station_information`
- Station status: `https://madrid.publicbikesystem.net/customer/gbfs/v3.0/station_status`
- Verified live 2026-06-21, TTL 9-30 seconds

Station information response (per station):
```json
{
  "station_id": "1406",
  "name": [{"text": "2 - Metro Callao", "language": "es"}],
  "short_name": [{"text": "2", "language": "es"}],
  "lat": 40.4204,
  "lon": -3.7057,
  "address": "Calle Miguel Moya nº 1",
  "capacity": 47
}
```

Station status response (per station):
```json
{
  "station_id": "1406",
  "num_vehicles_available": 11,
  "num_docks_available": 12,
  "is_installed": true,
  "is_renting": true,
  "is_returning": true
}
```

Join on `station_id`. Match stations by name substring (case-insensitive). Use `num_vehicles_available` for available bikes.

**Fallback — CityBikes API (no auth):**
- `https://api.citybik.es/v2/networks/bicimad`
- Returns all stations with `free_bikes` count in a single request
- Slightly delayed vs. official source, but simpler (single request, no join needed)

### Google Calendar: Private iCal URL

For a daily 8am print, the simplest approach with least setup:
- Get the secret iCal URL from Google Calendar settings
- Fetch and parse with `icalendar` + `recurring-ical-events` libraries
- No OAuth, no Google Cloud project, no token refresh
- Possible delay up to 12h (acceptable for a morning print of today's schedule)
- Store the iCal URL in `.env` as a secret

If real-time accuracy is needed later, upgrade to OAuth2 REST API with offline refresh token.

### Fun Fact: TBD

Options to research at implementation time:
- Wikipedia "On this day" API
- Quote of the day APIs
- Random facts API

---

## Requirements (EARS Format)

### System

| ID | Requirement |
|----|-------------|
| SYS-01 | When the system is triggered, it **shall** load the system config from `config.yaml`. |
| SYS-02 | When the system is triggered, it **shall** load the specified receipt config from `receipts/`. |
| SYS-03 | The system **shall** validate that all required secrets (declared by widgets in the receipt) are present in the environment at startup. |
| SYS-04 | If a required secret is missing, the system **shall** log an error and exit without printing. |
| SYS-05 | The system **shall** log all execution output (info, error, debug) to both stdout and a configurable log file. |
| SYS-06 | The system **shall** support multiple receipt configs, each triggered independently. |
| SYS-07 | The system **shall** expose a single entry point (`print_receipt`) that is trigger-agnostic. |

### Widgets

| ID | Requirement |
|----|-------------|
| WID-01 | Each widget **shall** be a class inheriting from `Widget` with a `render(params, context)` method returning `list[ESCPOSAction]`. |
| WID-02 | Each widget **shall** declare its required secrets as a `required_secrets` class variable. |
| WID-03 | Widgets in `src/widgets/` **shall** be autodiscovered via `__init_subclass__` + `pkgutil.iter_modules` at startup without explicit registration. |
| WID-04 | When a widget raises an exception during rendering, the system **shall** log the error and continue rendering remaining widgets. |
| WID-05 | Widgets **shall not** interact with the printer directly; they return actions only. |
| WID-06 | The system **shall** inject shared context (date, time) into each widget's `render` call. |
| WID-07 | Each widget **shall** declare an explicit `widget_type` class variable mapping to the receipt JSON `"type"` field. |

### Printer

| ID | Requirement |
|----|-------------|
| PRT-01 | The printer driver **shall** derive the set of valid actions from the configured printer profile using `profile.supports()`. |
| PRT-02 | The printer driver **shall** connect to the printer via network using the IP, port, timeout, and profile from `config.yaml`. |
| PRT-03 | If the printer is unreachable, the system **shall** log the error and exit gracefully (silent failure). |
| PRT-04 | The printer driver **shall** execute each `ESCPOSAction` by calling the corresponding `python-escpos` method. |
| PRT-05 | The printer driver **shall** reset formatting state (`set_with_default()`) between widgets to prevent style bleed. |
| PRT-06 | The printer driver **shall** call `open()` explicitly on construction for fast-fail detection. |

### Layout

| ID | Requirement |
|----|-------------|
| LAY-01 | The receipt config **shall** define layout options (header, separator style, cut behavior). |
| LAY-02 | When `header` is enabled, the system **shall** print the receipt name and current date/time at the top. |
| LAY-03 | When a separator is configured, the system **shall** insert it between each widget's output. |
| LAY-04 | When `cut_at_end` is enabled, the system **shall** append a cut action after all widget output. |

### Scheduling

| ID | Requirement |
|----|-------------|
| SCH-01 | The system **shall** be runnable via cron with no interactive input required. |
| SCH-02 | While running via cron, the system **shall** produce no output to stdout beyond what is captured in the log file. |

### Code Quality

| ID | Requirement |
|----|-------------|
| QUA-01 | All source code **shall** have strict type hints (mypy strict mode). |
| QUA-02 | All source code **shall** pass `black` formatting checks (line-length 88). |
| QUA-03 | All source code **shall** pass ruff linting (rulesets: E, W, F, I, N, UP, B, SIM, PTH, RUF). |
| QUA-04 | Unit test coverage **shall** be at minimum 80%. |
| QUA-05 | The project **shall** provide a Makefile with targets: `format`, `lint`, `test`, `build` (lint + test), `run`. |
| QUA-06 | The `build` target **shall** enforce linting and testing as requirements for success. |
| QUA-07 | A `.env.example` file **shall** be committed listing all required secrets with placeholder values. |
| QUA-08 | The project **shall** use `uv` for dependency management with a committed `uv.lock` file. |

### Stretch Goals

| ID | Requirement |
|----|-------------|
| STR-01 | The system **should** support an E2E test mode using `escpos.printer.Dummy` to capture output and snapshot-test the full action sequence for a given receipt config with mocked API responses. |
