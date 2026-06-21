# daily-receipt-printing

I check the same things every morning: weather, bike availability at stations near me, and my calendar. I wanted that information waiting for me on paper instead of pulling out my phone. So I hooked up a thermal receipt printer and built this.

It prints a personalized morning brief. You configure a receipt as a list of widgets, each one fetching live data and formatting it for a 48-column thermal printer. If one widget fails (API down, network timeout), the rest still print. The system is extensible. Adding a new widget is one file.

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd daily-receipt-printing
uv sync --extra calendar
cp .env.example .env        # add GOOGLE_CALENDAR_ICAL_URL if using the calendar widget
```

## Making a receipt

A receipt is a JSON file that defines which widgets to print and in what order. Create one in `receipts/`:

```json
{
  "name": "My Morning Brief",
  "layout": {
    "header": true,
    "separator": true,
    "cut_at_end": true,
    "columns": 48
  },
  "widgets": [
    {
      "type": "weather",
      "params": {"latitude": 40.4168, "longitude": -3.7038, "hours": 8}
    },
    {
      "type": "bicimad",
      "params": {"stations": [295, 151, 133]}
    },
    {
      "type": "calendar",
      "params": {}
    },
    {
      "type": "fun-fact",
      "params": {}
    }
  ]
}
```

### Built-in widgets

| Widget | What it does | Config |
|--------|-------------|--------|
| `weather` | Hourly forecast from Open-Meteo | `latitude`, `longitude`, `hours` |
| `bicimad` | Bike availability from Madrid BiciMad | `stations` (list of public station IDs) |
| `calendar` | Today's events from a Google Calendar iCal feed | Needs `GOOGLE_CALENDAR_ICAL_URL` in `.env` |
| `fun-fact` | Random fact (deterministic fallback if API is down) | None |

## Previewing

You can preview a receipt in the terminal without a printer:

```bash
make preview RECEIPT=receipts/patrick.json
```

```
             PATRICK'S DAILY BRIEF
             SUNDAY, JUNE 21, 2026
------------------------------------------------
Weather — 40.42, -3.70
Hour  Temp   Rain% Sky
----- -----  ----- -------
08:00 24C    0%    Clear
09:00 25C    0%    Clear
10:00 27C    0%    Clear
------------------------------------------------
BiciMad
 0 bikes - Hernani - Edgar Neville
 3 bikes - Orense 12
 1 bikes - Raimundo Fdez. Villaverde
------------------------------------------------
Calendar
All day  Team offsite
11:00  Standup
14:00  Design review
------------------------------------------------
Fun Fact
Honey never spoils. Archaeologists have found
3,000-year-old honey still edible.

================================================
```

## Printing

Configure your printer connection in `config.yaml`:

```yaml
printer:
  host: "192.168.0.200"
  port: 9100
  profile: "TM-T20II"
  timeout: 10
```

Then print:

```bash
make run RECEIPT=receipts/patrick.json
```

For automated daily printing, set up a cron job. See [docs/CRON.md](docs/CRON.md).

## Adding a widget

Create a file in `src/widgets/`:

```python
from widgets.widget import Widget
from core.actions import ESCPOSAction, TextAction
from core.context import Context

class MyWidget(Widget):
    widget_type = "my-widget"
    required_secrets = []  # or ["MY_API_KEY"] for keys in .env

    def render(self, params: dict, context: Context) -> list[ESCPOSAction]:
        # fetch data, format it, return actions
        return [TextAction(content="Hello from my widget\n")]
```

It gets autodiscovered. Add it to a receipt config and it prints:

```json
{"type": "my-widget", "params": {}}
```

## License

MIT
