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

- [ ] **Set up logging module** (`src/core/logging.py`)
  - Configure from config.yaml values
  - Dual handler: StreamHandler (stdout) + RotatingFileHandler
  - Timestamped format with level, module, message
  - Create log directory if not exists

- [ ] **Update `.gitignore`**
  - Add: `build/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, `logs/`, `.env`, `uv.lock` (or commit it — decide)

## Phase 1: Core Framework

- [ ] **Define `ESCPOSAction` dataclass** (`src/core/actions.py`)
  - Use a dataclass with `action: str` + `kwargs: dict` pattern, or individual typed dataclasses per action
  - Validate action type against printer profile capabilities at dispatch time
  - The driver maps each action to the corresponding `python-escpos` method call

- [ ] **Define `Context` dataclass** (`src/core/context.py`)
  - Fields: `date: datetime.date`, `time: datetime.time`, `receipt_name: str`
  - Created fresh each execution

- [ ] **Define `Widget` ABC** (`src/widgets/widget.py`)
  - `widget_type: str` class variable (mandatory, maps to JSON "type")
  - `required_secrets: list[str] = []` class variable
  - `_registry: dict[str, type[Widget]]` class variable
  - `__init_subclass__` for auto-registration (skip abstract classes, enforce widget_type, reject duplicates)
  - `render(self, params: dict, context: Context) -> list[ESCPOSAction]` abstract method
  - `get(widget_type: str) -> type[Widget]` class method for lookup

- [ ] **Implement widget autodiscovery** (`src/widgets/__init__.py`)
  - `discover_widgets()` using `pkgutil.iter_modules` on the widgets package directory
  - Skip `_`-prefixed modules
  - Wrap each import in try/except, log failures, continue loading others
  - Call `discover_widgets()` in `__init__.py`

- [ ] **Implement config loader** (`src/core/config.py`)
  - Load `config.yaml` with PyYAML
  - Load `.env` with python-dotenv
  - Load receipt JSON, validate structure
  - Collect required_secrets from all widgets in the receipt, check env for each

- [ ] **Implement widget runner** (`src/core/runner.py`)
  - Iterate receipt widget list
  - For each: look up class via `Widget.get(type)`, instantiate, call `render(params, context)`
  - Wrap each render in try/except — log error, append error placeholder text action, continue
  - Return aggregated list of actions

- [ ] **Implement layout engine** (`src/core/layout.py`)
  - Read layout config from receipt JSON
  - If `header`: prepend set(bold, center) + text(name + date) actions
  - If `separator`: insert separator actions (dashes line at column width) between widget outputs
  - If `cut_at_end`: append feed + cut actions
  - Use `printer.profile.get_columns("a")` for separator width

- [ ] **Implement printer driver** (`src/core/printer.py`)
  - Construct `Network(host, port, timeout, profile)` from config
  - Call `open()` explicitly for fast-fail
  - `execute(actions: list[ESCPOSAction])`: iterate actions, call corresponding methods
  - Call `set_with_default()` between widget action groups to reset formatting
  - Wrap in try/finally to ensure `close()`
  - For testing: accept `Dummy` printer instance (same interface)

- [ ] **Wire up `print_receipt(receipt_path: str)`** (`src/core/engine.py`)
  - Load config → load receipt → validate secrets → build context → run widgets → apply layout → execute on printer
  - Top-level try/except for printer connection errors → log and exit

- [ ] **Wire up `main.py` CLI** (`src/core/main.py`)
  - Accept receipt path as CLI argument (argparse)
  - Call `print_receipt(receipt_path)`
  - Exit code 0 on success, 1 on failure

## Phase 2: Widgets

- [ ] **Implement `weather` widget** (`src/widgets/weather.py`)
  - `widget_type = "weather"`
  - `required_secrets = []` (Open-Meteo needs no key)
  - Params: `location` (city name or lat/lon), `fields` (temperature, precipitation, etc.), `hours` (how many hours to show)
  - Use Open-Meteo geocoding API to resolve city name → lat/lon (cache or let user pass coords)
  - Fetch: `https://api.open-meteo.com/v1/forecast?latitude=X&longitude=Y&hourly=temperature_2m,precipitation_probability,weathercode&timezone=Europe/Madrid&forecast_days=1`
  - Format as table: hour | temp | rain% — using monospace text aligned to column width
  - Handle: API timeout, malformed response

- [ ] **Implement `bicimad` widget** (`src/widgets/bicimad.py`)
  - `widget_type = "bicimad"`
  - `required_secrets = []` (no auth needed)
  - Params: `stations` (list of station name substrings to match)
  - Primary: fetch GBFS v3.0 `station_information` + `station_status` from `madrid.publicbikesystem.net`, join on `station_id`
  - Fallback: fetch CityBikes `https://api.citybik.es/v2/networks/bicimad` (single request)
  - Match station names by substring (case-insensitive) — note GBFS names are localized arrays, extract `"es"` language entry
  - Output: station name + available bikes count (`num_vehicles_available` from GBFS, `free_bikes` from CityBikes)
  - Handle: API timeout, station not found (log warning, skip), `is_renting == false` stations

- [ ] **Implement `calendar` widget** (`src/widgets/calendar.py`)
  - `widget_type = "calendar"`
  - `required_secrets = ["GOOGLE_CALENDAR_ICAL_URL"]`
  - Add deps: `icalendar`, `recurring-ical-events`
  - Fetch iCal URL from env, parse with icalendar
  - Use `recurring_ical_events.of(cal).at(today)` to expand recurring events
  - Format: time + summary for each event, sorted by start time
  - Handle: fetch failure, parse error, empty calendar

- [ ] **Implement `fun-fact` widget** (`src/widgets/fun_fact.py`)
  - `widget_type = "fun-fact"`
  - `required_secrets = []`
  - Research at implementation time: Wikipedia "On this day", Useless Facts API, Quotable API
  - Pick one that's free, no-auth, reliable
  - Format: wrap text to column width using `textwrap`
  - Handle: API failure → fallback to a hardcoded set of facts

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
