# Tasks

## Phase 0: Project Scaffolding

- [x] **Set up `pyproject.toml`** with `uv`
  - Project metadata (name, version, requires-python >= 3.12)
  - Runtime deps: `python-escpos>=3.1`, `pyyaml`, `python-dotenv`, `requests`
  - Dev deps: `black>=24.0`, `ruff>=0.8`, `pytest>=8.0`, `pytest-cov>=6.0`, `mypy>=1.13`
  - `[tool.black]`: line-length 88, target-version py312
  - `[tool.ruff]`: line-length 88, select E/W/F/I/N/UP/B/SIM/PTH/RUF, ignore E501
  - `[tool.pytest.ini_options]`: testpaths=tests, --cov=src, --cov-fail-under=80
  - `[tool.mypy]`: strict=true, mypy_path="src", packages=["core","widgets"], ignore_missing_imports for escpos
  - Run `uv sync` to generate `uv.lock`

- [x] **Create Makefile**
  - `format`: `uv run black src tests && uv run ruff check --fix src tests`
  - `lint`: `uv run black --check src tests && uv run ruff check src tests && uv run mypy` (no path args — uses pyproject.toml config)
  - `test`: `uv run pytest`
  - `build`: depends on lint + test
  - `run`: `uv run python src/core/main.py` (accepts RECEIPT arg)
  - `clean`: remove build/, caches, __pycache__

- [x] **Create `.env.example`**
  - `GOOGLE_CALENDAR_ICAL_URL=https://calendar.google.com/calendar/ical/YOUR_CALENDAR_ID/private-XXXXXXXX/basic.ics`
  - (BiciMad: no secret needed — CityBikes/GBFS have no auth)
  - (Weather: no secret needed — Open-Meteo has no auth)

- [x] **Create `config.yaml`** with defaults
  - `printer.host`: "192.168.0.200"
  - `printer.port`: 9100
  - `printer.profile`: "TM-T20II"
  - `printer.timeout`: 10
  - `logging.level`: "INFO"
  - `logging.file`: "logs/daily-receipt.log"

- [x] **Set up logging module** (`src/core/log_config.py`)
  - Configure from config.yaml values via `setup_logging(config)` + `get_logger(name)`
  - Dual handler: StreamHandler (stdout) + RotatingFileHandler (5MB, 5 backups)
  - Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
  - Creates log directory via pathlib if not exists
  - Named `log_config.py` (not `logging.py`) to avoid shadowing stdlib

- [x] **Update `.gitignore`**
  - Added: `__pycache__/`, `*.pyc`, `.coverage`, `build/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `htmlcov/`, `logs/`, `.env`
  - `uv.lock` is committed (needed for reproducible installs)

## Phase 1: Core Framework

- [x] **Define `ESCPOSAction` dataclass** (`src/core/actions.py`)
  - Abstract base class (ABC) with `action: str = field(init=False)`, set via `__post_init__` in each subclass
  - Individual typed dataclasses per action: SetAction, TextAction, FeedAction, ImageAction, QRAction, BarcodeAction, CutAction
  - `ActionList = list[ESCPOSAction]` type alias
  - Validation of action type against printer profile deferred to driver dispatch time

- [x] **Define `Context` dataclass** (`src/core/context.py`)
  - Frozen dataclass: `date: datetime.date`, `time: datetime.time`, `receipt_name: str`
  - Factory: `build_context(receipt_name: str) -> Context` captures current datetime
  - Immutable — widgets cannot mutate shared context

- [x] **Define `Widget` ABC** (`src/widgets/widget.py`)
  - `widget_type: ClassVar[str]` (mandatory, maps to JSON "type")
  - `required_secrets: ClassVar[list[str]] = []`
  - `_registry: ClassVar[dict[str, type[Widget]]] = {}`
  - `__init_subclass__` for auto-registration (skip abstract classes, enforce widget_type, reject duplicates with named error)
  - `render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]` abstract method
  - `get(widget_type: str) -> type[Widget]` class method for lookup (raises KeyError)

- [x] **Implement widget autodiscovery** (`src/widgets/__init__.py`)
  - `discover_widgets()` using `pkgutil.iter_modules` on the widgets package directory
  - Skips `_`-prefixed modules and the `widget` base module
  - Wraps each import in try/except, logs failures via logger.exception, continues
  - Called at import time; re-exports `Widget`

- [x] **Implement config loader** (`src/core/config.py`)
  - `load_system_config(path)` — loads YAML, raises FileNotFoundError if missing
  - `load_receipt_config(path)` — loads JSON, raises FileNotFoundError/ValueError
  - `validate_secrets(receipt_config)` — collects all widget required_secrets, raises OSError listing ALL missing (deduplicated)
  - Module-level `load_dotenv()` loads `.env` on import
  - 16 tests, 100% coverage on config.py

- [x] **Implement widget runner** (`src/core/runner.py`)
  - `run_widgets(receipt_config, context)` iterates receipt widget list
  - For each: look up class via `Widget.get(type)`, instantiate, call `render(params, context)`
  - Entire per-widget block (including type/params extraction) wrapped in try/except for full failure isolation
  - On failure: logs error, appends `TextAction` placeholder `"[widget '{type}' failed]"`, continues
  - Returns aggregated flat list of actions
  - 9 tests, 100% coverage

- [x] **Implement layout engine** (`src/core/layout.py`)
  - `apply_layout(widget_action_groups, receipt_config, context)` wraps widget output with layout chrome
  - Layout config from receipt JSON with defaults: `header=True`, `separator=True`, `cut_at_end=True`, `columns=48`
  - Header: bold/center name + formatted date (`%A, %B %d, %Y`), then reset
  - Separator: `"-" * columns + "\n"` between non-empty widget groups (and after header)
  - Cut: `FeedAction(lines=3)` + `CutAction()` at end
  - Columns from receipt config (printer-agnostic — no coupling to profile)
  - 11 tests, 100% coverage

- [x] **Implement printer driver** (`src/core/printer.py`)
  - `connect_printer(config)` constructs `Network(host, port, timeout, profile)` and calls `open()`
  - `execute_actions(printer, actions)` dispatches each ESCPOSAction via isinstance to the correct printer method
  - `_dispatch_action` handles all 7 action types; raises `ValueError` on unknown
  - Calls `set_with_default()` after execution to reset formatting
  - `print_actions(config, actions)` wraps in try/finally ensuring `close()`
  - Accepts `Network | Dummy` for testability
  - 22 tests, 100% coverage

- [x] **Wire up `print_receipt(receipt_path: str)`** (`src/core/engine.py`)
  - `print_receipt(receipt_path, config_path="config.yaml")` orchestrates full pipeline
  - Load system config → load receipt → validate secrets → build context → run widgets grouped → apply layout → print
  - `_run_widgets_grouped()` collects per-widget action lists for layout separator insertion
  - Printer connection errors (OSError) caught and logged without crashing
  - 13 tests, 100% coverage

- [x] **Wire up `main.py` CLI** (`src/core/main.py`)
  - argparse with positional `receipt` arg and optional `--config` (default: "config.yaml")
  - Calls `print_receipt(receipt_path, config_path=config)`
  - Exit code 0 on success, 1 on any exception (logged)
  - 6 tests, 100% coverage

## Phase 2: Widgets

- [x] **Implement `weather` widget** (`src/widgets/weather.py`)
  - `widget_type = "weather"`, `required_secrets = []`
  - Params: `latitude`/`longitude` (direct coords) or `location` (city name via geocoding), `hours` (default 12), `timezone` (default "Europe/Madrid")
  - Geocoding via Open-Meteo `geocoding-api.open-meteo.com/v1/search`
  - Forecast via `api.open-meteo.com/v1/forecast` (temperature, precipitation_probability, weathercode)
  - Formats as fixed-width table: Hour | Temp | Rain% | Sky (weather code description)
  - Filters to hours from current time onward; `fields` param omitted (all 3 columns fit 48-col receipt)
  - All errors (timeout, connection, malformed response) → `[weather unavailable]` placeholder
  - 16 tests, 99% coverage

- [x] **Implement `bicimad` widget** (`src/widgets/bicimad.py`)
  - `widget_type = "bicimad"`, `required_secrets = []`
  - Params: `stations` (list of station name substrings to match, case-insensitive)
  - Primary: GBFS v3.0 from `madrid.publicbikesystem.net` (station_information + station_status joined on station_id)
  - Fallback: CityBikes API (`api.citybik.es/v2/networks/bicimad`)
  - Localized name extraction (prefers "es", falls back to first entry)
  - Skips `is_renting=false` stations with logged warning; unmatched substrings logged and skipped
  - All APIs fail → `[bicimad unavailable]` placeholder
  - 17 tests, 99% coverage

- [x] **Implement `calendar` widget** (`src/widgets/calendar.py`)
  - `widget_type = "calendar"`, `required_secrets = ["GOOGLE_CALENDAR_ICAL_URL"]`
  - Deps: `icalendar`, `recurring-ical-events` (optional extra: `uv sync --extra calendar`)
  - Fetches iCal from `GOOGLE_CALENDAR_ICAL_URL` env var, parses with icalendar
  - Expands recurring events via `recurring_ical_events.of(cal).at(context.date)`
  - Sorts all-day events first, then timed events by start time
  - Format: "All day  Summary" or "HH:MM  Summary", with "No events today" fallback
  - All errors → `[calendar unavailable]` placeholder
  - 12 tests, 100% coverage

- [x] **Implement `fun-fact` widget** (`src/widgets/fun_fact.py`)
  - `widget_type = "fun-fact"`, `required_secrets = []`
  - Uses Useless Facts API (`uselessfacts.jsph.pl/api/v2/facts/random`, free, no auth)
  - On API failure: deterministic fallback from 10 hardcoded facts (sha256 of date → stable index)
  - Text wrapped to configurable `columns` (default 48) via `textwrap.fill()`
  - 9 tests, 100% coverage

## Phase 3: Quality & Polish

- [ ] **Unit tests for core modules**
  - `tests/core/test_actions.py` — action creation, validation
  - `tests/core/test_config.py` — config loading, secret validation, missing file handling
  - `tests/core/test_runner.py` — widget execution, failure isolation, context injection
  - `tests/core/test_layout.py` — header/separator/cut generation
  - `tests/core/test_printer.py` — action dispatch to Dummy printer, formatting reset
  - `tests/core/test_engine.py` — end-to-end with Dummy printer + mocked widgets

- [ ] **Unit tests for widgets**
  - Mock HTTP responses (use `unittest.mock.patch` on `requests.get`)
  - Test happy path + API failure + malformed response for each widget
  - Verify returned actions are valid ESCPOSAction instances

- [ ] **E2E snapshot test** (stretch goal)
  - Use `Dummy` printer to capture raw byte output
  - Mock all external APIs with fixture data
  - Assert action list matches saved snapshot (pytest-snapshot or manual JSON comparison)
  - Enables "what would this receipt look like" without printing

- [ ] **Cron setup documentation**
  - Crontab entry: `0 8 * * 1-5 /path/to/uv run python /path/to/src/core/main.py /path/to/receipts/patrick.json >> /path/to/logs/cron.log 2>&1`
  - Note: ensure `.env` is loaded (python-dotenv handles this in code)
  - Note: use absolute paths in cron

- [ ] **Update CLAUDE.md** with final commands, architecture, and directory structure

## Phase 4: Stretch

- [ ] **Visual receipt preview** — render action list to a plain-text file mimicking 48-col receipt output
- [ ] **Receipt diff tool** — compare two snapshot outputs for regression detection
