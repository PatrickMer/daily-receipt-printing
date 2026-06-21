# Cron Setup

Print a daily receipt at 8am on weekdays.

## Prerequisites

- `uv` installed and on PATH
- Dependencies synced: `uv sync --extra calendar`
- `.env` file configured (python-dotenv loads it automatically at runtime)
- Printer reachable at configured IP (default: 192.168.0.200)

## Crontab Entry

```cron
0 8 * * 1-5 cd /path/to/daily-receipt-printing && PYTHONPATH=src uv run python src/core/main.py receipts/patrick.json >> logs/cron.log 2>&1
```

Replace `/path/to/daily-receipt-printing` with the absolute path to your clone.

## Installing

```bash
crontab -e
```

Paste the entry above, save, and verify with:

```bash
crontab -l
```

## Troubleshooting

**Check logs:** The app logs to `logs/daily-receipt.log` (rotating). Cron-specific stdout/stderr goes to `logs/cron.log`.

**Test manually:**

```bash
cd /path/to/daily-receipt-printing
PYTHONPATH=src uv run python src/core/main.py receipts/patrick.json
```

**Verify printer connectivity:**

```bash
ping -c 1 192.168.0.200
```

**Common issues:**

- `uv` not found in cron's PATH -- use the full path (e.g. `/Users/you/.local/bin/uv`) or add a `PATH=...` line at the top of your crontab.
- Printer unreachable -- check it's powered on and on the same network.
