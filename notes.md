## Notes

The best solution to talk to the printer is using:
https://github.com/python-escpos/python-escpos
https://python-escpos.readthedocs.io/en/latest/user/methods.html

Its plug and play.
I was able to print successfully and it cuts the paper.
`python3 escpos-test.py`

Use this profile:
https://python-escpos.readthedocs.io/en/latest/printer_profiles/available-profiles.html#tm-t20ii
There seems to also be a 48-col wdith profile that I could try out.


Alternatives considered and not used:
https://github.com/OpenPrinting/pycups - this is a python wrapper for the CUPS API, probably quite hard to use since its just a full passthrough wrapper. See `cupstree.py`.
https://www.cups.org/doc/options.html - commands `lp` and `lpr` could've worked pretty easily but I'd have to write my own wrapper.


---
## Design ideas

The user wants to see a receipt.
A receipt is a static config.
Each user has one receipt.

There is a global config that is passed to every widget (e.g. date, time, username, language, common things)

The widget can define its own input schema in json
A widget takes an input of its input config + the global config.
A widget returns the content it wants to display on the receipt.

Decision:
Do all widgets have to be near real time?
When a user chooses to print a receipt, there shouldn't be more than a 5-10 sec delay. 
For now, we require the widgets to adhere to this time limit.
If in future this doesn't work, we pre-compute widgets/receipts and serve cached versions.

---

Components
- widgets
  - widget.py (parent class)
    > method: `render(config, context) -> List[ESCPOSAction]`
  - weather.py
  - bicimad.py
  - calendar.py
  - fun-fact.py
- receipts
  - patrick.json (user receipt config)
- schemas
  - receipt.schema.json (top-level receipt shape)
  - widgets/
    - weather.schema.json
    - bicimad.schema.json
    - calendar.schema.json
- core
  - generate_printable_receipt.py
  - connect_printer.py
  - load_configs.py
  - main.py


Widgets are the way of adding functionality to a receipt.
A widget's input contract is defined in `receipts/schema.json` (in [json schema](https://json-schema.org/understanding-json-schema/reference)).
The Core is responsible for injecting shared context (`date` and `time`) into the widget at the moment of execution.

Widgets in a receipt are completely independent.
Widget failures are handled gracefully, other widgets will be displayed.

To keep widgets printer-agnostic, they return a list of objects that map directly to `python-escpos` methods. The Core iterates through this list and calls the driver.

Example Output Schema:
{
  "version": 1,
  "actions": [
    {"action": "text", "content": "Hello World\n", "align": "center"},
    {"action": "barcode", "code": "12345", "type": "EAN13"},
    {"action": "cut", "mode": "PART"}
  ]
}

## Appendix / Draft snippets

**`schemas/receipt.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Receipt",
  "type": "object",
  "required": ["receipt"],
  "properties": {
    "receipt": {
      "type": "object",
      "required": ["name", "widgets"],
      "properties": {
        "name": { "type": "string" },
        "widgets": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["type", "params"],
            "properties": {
              "type": { "type": "string" },
              "params": { "type": "object" }
            }
          }
        }
      }
    }
  }
}
```

**`schemas/widgets/weather.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WeatherWidgetParams",
  "type": "object",
  "required": ["location", "fields", "period"],
  "properties": {
    "location": { "type": "string" },
    "fields": {
      "type": "array",
      "items": { "type": "string", "enum": ["temperature", "precipitation", "wind", "humidity"] },
      "minItems": 1
    },
    "period": { "type": "string", "enum": ["hourly", "daily"] }
  }
}
```

**`receipts/patrick.json`**

```json
{
  "receipt": {
    "name": "patrick",
    "widgets": [
      {
        "type": "common",
        "params": {
          "date": "auto",
          "time": "auto"
        }
      },
      {
        "type": "weather",
        "params": {
          "location": "madrid",
          "fields": ["temperature", "precipitation"],
          "period": "hourly"
        }
      },
      {
        "type": "bicimad",
        "params": {
          "stations": ["hernani", "orense"]
        }
      },
      {
        "type": "calendar",
        "params": {
          "api_key_env": "GOOGLE_CALENDAR_API_KEY"
        }
      }
    ]
  }
}
```
