# Audio Search - Terminal Scraper Tool

Multi-scraper search tool for audio equipment across multiple marketplaces.For bash termial.

## Features

Searches across:
- **Blocket** - Swedish marketplace
- **Tradera** - Swedish auction site
- **Facebook Marketplace** - Facebook marketplace (Stockholm region)
- **HifiTorget** - Swedish hifi marketplace
- **HiFiShark** - International HiFi equipment search engine (Sweden filter)
- **Reference Audio**, **Ljudmakarn**, **HiFi-Punkten** - Swedish retailers (Ashop platform)
- **Rehifi** and **AudioPerformance** - Refurbished HiFi (Starweb)
- **HiFi Puls**, **Akkelis Audio**, **Lasses HiFi** - Demo/Fyndhörna retailers
- **HiFi Experience** and **AudioConcept** - WooCommerce-based demo/begagnat catalogs

## Installation

1. Install Python dependencies:
```bash
pip install --break-system-packages -r requirements.txt
```

2. Install Playwright browsers (required for Facebook and HiFiShark):
```bash
python3 -m playwright install chromium
```

## Usage

Search for one or more terms:

```bash
# Single search term
python3 HIFI_search.py -s "yamaha receiver"

# Multiple search terms
python3 HIFI_search.py -s "speakers" -s "amplifier" -s "turntable"
```

Or make it executable and run directly:
```bash
chmod +x HIFI_search.py
./HIFI_search.py -s "your search term"
```

## Output Format

Results are displayed grouped by marketplace with:
- Clickable URLs (if your terminal supports hyperlinks)
- Plain URLs for copy-paste
- Price information (when available)
- Description (when available)
- Posted date (when available)

## Requirements

- Python 3.7+
- See `requirements.txt` for package dependencies
