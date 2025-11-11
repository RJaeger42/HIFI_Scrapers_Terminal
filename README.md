# Audio Search – Terminal Scraper Tool

Audio Search is a terminal-first metasearch that fans out to 15 Swedish and international marketplaces to help you spot interesting HiFi listings fast. It bundles lightweight BeautifulSoup scrapers with Playwright-powered browser automation where needed.

## Supported Sources

| Site | Notes |
| --- | --- |
| Blocket, Tradera | Classifieds & auctions (requests + Playwright fallbacks)
| Facebook Marketplace | Chromium/Playwright session scoped to Stockholm region
| HifiTorget, HiFiShark | Specialty HiFi marketplaces with Swedish filters
| Reference Audio, Ljudmakarn, HiFi-Punkten | Ashop-based demo/begagnat feeds
| Rehifi, AudioPerformance | Starweb storefronts (refurbished gear)
| HiFi Experience, AudioConcept | WooCommerce demo/b-stock pages
| Lasses HiFi, Akkelis Audio, HiFi Puls | Retail demo/fyndhörna listings

## Requirements

- Python 3.9 or later (3.11 recommended for faster asyncio)
- `pip` plus a virtual environment tool (e.g. `venv`)
- Playwright browsers installed locally for the Chromium-backed scrapers

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
```

> If you cannot use virtualenvs (e.g. system-wide deployment) append `--break-system-packages` to the `pip install` command.

## Usage

All searches require at least one `-s/--search` argument. Synonyms are auto-expanded (e.g. `amp` triggers `amplifier` and `förstärkare`).

```bash
# Fast single query
python3 HIFI_search.py -s "yamaha receiver"

# Multiple focused searches
python3 HIFI_search.py -s "mcintosh" -s "horn speakers" -d 7 --sort price

# Restrict to a subset of scrapers
python3 HIFI_search.py -s "dac" -i blocket -i "hifi shark"
```

| Flag | Description |
| --- | --- |
| `-s/--search TEXT` | Add one or more search phrases (repeatable)
| `-d/--days INT` | Only keep results newer than N days
| `-i/--include NAME` | Only run scrapers whose name matches `NAME` (partial/case-insensitive)
| `-e/--exclude NAME` | Skip selected scrapers (same matching rules as include)
| `--sort {date,site,price}` | Order merged output; defaults to newest first
| `--debug` | Verbose logging plus per-scraper timing info

Make the entrypoint executable if you prefer `./HIFI_search.py` style invocations:

```bash
chmod +x HIFI_search.py
./HIFI_search.py -s "vinyl" --sort site
```

## Output

Each scraper prints a colored block that contains:
- OSC 8 hyperlinks (clickable in iTerm2, Windows Terminal, etc.) plus plaintext URLs
- Price, posted/updated date (normalized to ISO format when available)
- Seller/site metadata and a short excerpt of the description

Timeouts and scraper errors are surfaced inline so you can quickly see which provider misbehaved during a run.

## Troubleshooting

- **Playwright fails to launch** – rerun `python3 -m playwright install chromium` and make sure `libglib2.0`, `libnss3`, and other browser dependencies exist on your system.
- **Facebook results empty** – log into Facebook in a regular Chromium profile first; Marketplace throttles anonymous sessions heavily.
- **Rate limits / CAPTCHAs** – space out repeated searches or exclude problematic scrapers with `-e` flags.
- **Verbose diagnostics** – pass `--debug` to print scraper-by-scraper timing and the normalized query list.

## Contributing & Next Steps

- `ROADMAP.md` holds the active backlog (price filtering, exports, cached history, etc.).
- Please clean local artifacts (`__pycache__`, browser traces, debug logs) before opening a PR—this repo now ships with those removed.
- Issues and feature ideas are welcome once the documentation in this file stays in sync with new CLI flags.
