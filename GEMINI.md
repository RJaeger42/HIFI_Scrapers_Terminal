# GEMINI.md: HIFI Scrapers Terminal

This document provides a comprehensive overview of the HIFI Scrapers Terminal project, intended as a guide for future development and maintenance.

## Project Overview

This project is a Python-based command-line tool designed for meta-searching across multiple Swedish and international HIFI audio marketplaces. It aggregates listings from various sources, providing a unified interface for finding used and demo audio equipment.

The core technologies used are:
*   **Python 3:** The primary programming language.
*   **asyncio:** Used for running scrapers concurrently to improve performance.
*   **requests & BeautifulSoup4:** For scraping websites that serve static or server-rendered HTML content.
*   **Playwright:** For browser automation to scrape websites that rely heavily on JavaScript for dynamic content loading (e.g., Blocket, Facebook Marketplace).

The architecture is modular, consisting of a main orchestrator script (`HIFI_search.py`) that manages the command-line interface and coordinates the execution of individual scrapers located in the `Scrapers/` directory.

## Building and Running

### Setup

1.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Playwright Browsers:**
    The project uses Playwright with Chromium for some scrapers.
    ```bash
    python3 -m playwright install chromium
    ```

### Running the Tool

The main entry point is `HIFI_search.py`. Searches are initiated using the `-s` or `--search` flag.

**Examples:**

*   **Simple search:**
    ```bash
    python3 HIFI_search.py -s "yamaha receiver"
    ```

*   **Multiple searches, filtered by date and sorted by price:**
    ```bash
    python3 HIFI_search.py -s "mcintosh" -s "horn speakers" -d 7 --sort price
    ```

*   **Include or exclude specific sites:**
    ```bash
    # Only search Blocket and Tradera
    python3 HIFI_search.py -s "dac" -i blocket -i tradera

    # Search all sites except Facebook
    python3 HIFI_search.py -s "turntable" -e facebook
    ```

## Development Conventions

*   **Modular Architecture:** The project is organized with a clear separation of concerns. `HIFI_search.py` handles the CLI, orchestration, and result presentation. The `Scrapers/` directory contains the logic for individual site scraping.
*   **Scraper Design:**
    *   All scrapers should inherit from the `BaseScraper` class (defined in `base.py`).
    *   For common e-commerce platforms (e.g., Ashop, Starweb, WooCommerce), scrapers should use the shared base classes provided in `Scrapers/common.py` to reduce code duplication.
    *   Scrapers for JavaScript-heavy sites should use `playwright` for robust browser automation, as seen in `Scrapers/blocket.py`.
    *   Each scraper is responsible for fetching and parsing data from its target site and returning a list of `ListingResult` objects.
*   **Asynchronous Operations:** The `asyncio` library is used to run all scraper searches concurrently. New scrapers should have an `async def search(...)` method. For blocking I/O operations within a scraper, use `asyncio.to_thread` to avoid blocking the event loop.
*   **Error Handling:** Each scraper should handle its own potential errors (e.g., network issues, timeouts, changes in website HTML structure) gracefully. The main application will report errors on a per-scraper basis without crashing the entire search process.
*   **Code Style:**
    *   The codebase follows standard Python conventions (PEP 8).
    *   Type hints are used throughout the project (`List`, `Optional`, `Dict`, etc.) and should be included in new code.
*   **Dependencies:** Project dependencies are managed in `requirements.txt`.
