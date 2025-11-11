# Audio Search Project Roadmap

## Project Overview
**Audio Search** is a terminal-based multi-marketplace scraper for searching audio equipment across 5 different platforms (Blocket, Tradera, Facebook Marketplace, HifiTorget, and HiFiShark). Built with Python, async scrapers, and Playwright for dynamic content.

**Current Status:** Core functionality working with recent enhancements for sorting and default site behavior.

---

## Phase 1: Foundation & Core Features ✓ (Complete)

### Search Infrastructure
- [x] Multi-threaded async scraper architecture
- [x] Base scraper class with common functionality
- [x] Individual scrapers for 5 marketplaces
- [x] Error handling and retry logic
- [x] Timeout protection (60-second per scraper)

### Platform Support
- [x] Blocket.se (BeautifulSoup)
- [x] Tradera.com (BeautifulSoup)
- [x] Facebook Marketplace (Playwright)
- [x] HifiTorget.se (BeautifulSoup)
- [x] HiFiShark.com (Playwright)

### Output & Formatting
- [x] Tabular result display with alignment
- [x] Clickable hyperlinks in terminal (OSC 8 protocol)
- [x] Color-coded output (error, warning, info, success)
- [x] Date parsing (Swedish & English formats, relative dates)

---

## Phase 2: User Features ✓ (Recent Additions)

### Search Options
- [x] Multiple search terms (`-s` flag, repeatable)
- [x] Date filtering (`-d` days back)
- [x] Include specific sites (`-i` flag, repeatable)
- [x] Exclude specific sites (`-e` flag, repeatable)
- [x] All scrapers enabled by default

### Result Sorting
- [x] Sort by date (newest first) - default
- [x] Sort by site (alphabetical)
- [x] Sort by price (lowest first)
- [x] Proper null handling in sorting

### CLI & Documentation
- [x] Help text with examples (`--help`)
- [x] Clear error messages
- [x] Usage examples in help

---

## Phase 3: Planned Enhancements

### Short Term (Next 1-2 weeks)

#### 3.1 Enhanced Filtering
- [ ] Price range filtering (`--min-price` and `--max-price`)
- [ ] Location/region filtering (especially for FB Marketplace)
- [ ] Condition filtering (new, used, etc.) where available
- [ ] Seller rating/review filtering

#### 3.2 Data Export & Persistence
- [ ] Export to CSV format
- [ ] Export to JSON format
- [ ] Export to HTML report
- [ ] Save search results to local cache
- [ ] Search history tracking

#### 3.3 User Experience
- [ ] Progress indicators during multi-site searches
- [ ] Color-coded result highlights (e.g., best prices)
- [ ] Result pagination for large result sets
- [ ] Result count summary by site
- [ ] Quiet mode (`-q` flag) for scripting

### Medium Term (2-4 weeks)

#### 3.4 Advanced Search Features
- [ ] Regex pattern support for search queries
- [ ] Saved search profiles (JSON config files)
- [ ] Search alerts/notifications
- [ ] Fuzzy matching for typo tolerance
- [ ] Search term synonyms (e.g., "amp" → "amplifier")

#### 3.5 Database Integration
- [ ] SQLite database for result caching
- [ ] Duplicate detection across scrapers
- [ ] Price history tracking
- [ ] Database schema for listings

#### 3.6 Scraper Improvements
- [ ] Better condition/description parsing
- [ ] Seller contact info extraction (where available)
- [ ] Image download capability
- [ ] More robust date parsing
- [ ] Rate limiting to be respectful to servers

### Medium-Long Term (1-2 months)

#### 3.7 Web Interface
- [ ] Flask/FastAPI web server
- [ ] Web-based search UI
- [ ] Result visualization (charts, graphs)
- [ ] API endpoints for external integration
- [ ] Mobile-responsive design

#### 3.8 Notifications & Automation
- [ ] Email alerts for new listings
- [ ] Telegram/Slack bot integration
- [ ] Automatic daily scheduled searches
- [ ] Webhook support
- [ ] Smart notifications (only high-value deals)

#### 3.9 Performance & Reliability
- [ ] Connection pooling for HTTP requests
- [ ] Proxy rotation support
- [ ] User-agent rotation
- [ ] Better error recovery and retries
- [ ] Logging to file
- [ ] Performance metrics/benchmarking

### Long Term (2-3 months+)

#### 3.10 Machine Learning & Analytics
- [ ] Price trend analysis
- [ ] Deal detection (anomaly detection for prices)
- [ ] Recommendation engine
- [ ] Market analysis reports
- [ ] Seller reputation scoring

#### 3.11 Platform Expansion
- [ ] Additional Swedish marketplaces (Bukowskis, etc.)
- [ ] International sites (eBay, Reverb, etc.)
- [ ] Category-specific sites
- [ ] RSS feed support

#### 3.12 Configuration & Customization
- [ ] Config file support (YAML/TOML)
- [ ] Custom column selection
- [ ] Theme support for output
- [ ] Plugin system for custom scrapers
- [ ] Custom CSS for web UI

#### 3.13 Additional web sites

| Site | Stack & Structure | Proposed Strategy | Notes / Dependencies | Status |
|------|-------------------|-------------------|----------------------|--------|
| [Reference Audio](https://www.referenceaudio.se/kategori/935/begagnat) | Ashop storefront, fully server-rendered HTML with predictable product cards and `?page=` pagination | Reuse existing requests + BeautifulSoup stack. Implement paginator by following `?page=` links until no results, parse `.product` blocks for title, price, link, image, breadcrumb for location. | Requires maintaining session cookie automatically set by storefront. | Implemented |
| [Rehifi](https://www.rehifi.se/) | Starweb (server-side rendered). Category pages expose full product data in markup, pagination via `?page=` params. | Requests + BeautifulSoup. Detect relevant category IDs by hitting search endpoint `?q=`. Parse `.product` grid, price spans, and availability text. | Respect `cache-control` by spacing requests (already handled by BaseScraper rate limiting). | Implemented |
| [HiFiPuls Demo/Begagnat](https://www.hifipuls.se/114-demo-begagnat) | PrestaShop, product listing in HTML (cards with `<article>`). | Requests + BeautifulSoup. Follow `?p=` for pagination. Extract vendor-provided condition text, price block `.price`. | Need to decode `&nbsp;` separators and convert Swedish currency formatting. | Implemented |
| [Esoterisk HiFi](https://esoterisk-hifi.se/begagnad-inbyten/) | WordPress + WooCommerce. Product list available in HTML and via `wp-json/wp/v2/product`. | Prefer HTML scraping to avoid auth; parse `.product` tiles. If site adds lazy loading, fallback to WP REST by calling `.../wp-json/wp/v2/product?per_page=50&status=publish&category=begagnad-inbyten`. | Use requests; no Playwright required. | Pending (site blocks public APIs) |
| [Ljudmakarn Fyndhörnan](https://www.ljudmakarn.se/kategori/107/fyndhornan) | Same Ashop platform as Reference Audio. | Share parser utilities with Reference Audio (common CSS classes). Possibly factor reusable `AshopScraperMixin`. | Handle VAT-inclusive price text. | Implemented |
| [AudioPerformance Begagnad HiFi](https://www.audioperformance.se/category/begagnad-hifi) | Starweb storefront (same as Rehifi). | Reuse Starweb parser helper to avoid duplication. | Need to include brand info from subtitle text. | Implemented |
| [Akkelis Audio](https://www.akkelisaudio.com/fyndhornan/) | Custom/WordPress site with static list of cards; moderate page size. | Requests + BeautifulSoup. Parse `.product` cards, use `<span class="price">`. | Some prices denote “Såld”; filter those out. | Implemented |
| [HiFi Experience](https://www.hifiexperience.se/produktkategori/begagnad-hifi/) | WooCommerce with infinite scroll (but initial page contains all products). | Requests + BeautifulSoup. If pagination occurs, rely on `?paged=` query parameter. | Titles often include condition; propagate to description. | Implemented (WooCommerce Store API) |
| [Audio Concept Demo & Begagnat](https://audioconcept.se/product-category/demo-och-begagnat/) | WooCommerce, similar to HiFi Experience. | Same WooCommerce parser module. May need to fetch additional pages if `max_num_pages > 1`. | Contains SEK and EUR prices; convert to SEK when currency symbol detected. | Implemented (WooCommerce Store API) |
| [HiFi-Punkten](https://www.hifi-punkten.se/kategori/1/produkter) | Ashop storefront. | Reuse Ashop parser module. | Some listings have multiple price tiers; take lowest shown. | Implemented |
| [Lasses HiFi](https://lasseshifi.se/collections/erbjudande) | Shopify. Data accessible via `https://lasseshifi.se/collections/erbjudande/products.json?page=N`. | Use Shopify JSON endpoint via requests to avoid HTML parsing. Iterate `page` until response empty. | Prices returned in SEK; include `compare_at_price` delta in description when present. | Implemented |

**Implementation Notes**
- All sites can be handled with existing Requests + BeautifulSoup stack; Playwright/Scrapy are not required at this stage.
- Create lightweight helper mixins for recurring platforms (Ashop, Starweb, WooCommerce) to avoid duplication.
- Shopify JSON access requires no auth but respect rate limits (add short sleep between pages if needed).

---

## Architecture & Technical Improvements

### Code Quality
- [ ] Unit tests (pytest)
- [ ] Integration tests
- [ ] Docker containerization
- [ ] GitHub Actions CI/CD
- [ ] Code coverage reporting
- [ ] Type hints throughout (mypy compliance)

### Documentation
- [ ] API documentation (docstrings)
- [ ] Architecture documentation
- [ ] Deployment guide
- [ ] Contributing guidelines
- [ ] Video tutorials

### Monitoring & Observability
- [ ] Structured logging
- [ ] Performance monitoring
- [ ] Error tracking (Sentry integration)
- [ ] Health checks for scrapers
- [ ] Metrics dashboard

---

## Known Issues & Technical Debt

### Current Issues
- Facebook Marketplace scraper unreliable (DOM changes frequently)
- HiFiShark pagination sometimes returns duplicate results
- Date parsing edge cases with ambiguous formats
- No validation of Blocket/Tradera pricing accuracy

### Technical Debt
- Some code duplication in scraper classes (refactor base class)
- Limited test coverage
- Error messages could be more user-friendly
- Hard-coded timeouts (should be configurable)
- No graceful handling of network failures beyond timeouts

---

## Priority Matrix

### High Priority / High Impact
1. Price range filtering
2. CSV/JSON export
3. Search profiles/saved searches
4. Database caching (reduce scraper load)
5. Better error recovery

### High Priority / Medium Impact
1. Web interface
2. Email notifications
3. Docker support
4. Unit tests
5. Configuration file support

### Medium Priority / High Impact
1. Additional marketplace support
2. Performance optimization
3. Logging infrastructure
4. Price history tracking
5. Duplicate detection

### Medium Priority / Medium Impact
1. Web API
2. Telegram bot
3. Recommendation engine
4. Theme/customization
5. Plugin system

---

## Metrics & Success Criteria

### User-Facing
- [ ] Search completes in < 30 seconds for all 5 sites
- [ ] Zero false results (accurate scraping)
- [ ] Support for 10+ search terms simultaneously
- [ ] Export formats working for 1000+ results

### Technical
- [ ] Test coverage > 70%
- [ ] No unhandled exceptions in normal usage
- [ ] Memory usage < 500MB for typical searches
- [ ] Support graceful degradation (one scraper down = other 4 work)

### Project Health
- [ ] GitHub repo with clear documentation
- [ ] Contributions guide for community developers
- [ ] Release schedule (monthly updates)
- [ ] Community engagement (issues/discussions)

---

## Milestone Timeline

| Milestone | Target | Goals |
|-----------|--------|-------|
| **v0.2** | Week 1-2 | Price filtering, CSV export, search profiles |
| **v0.3** | Week 3-4 | Web interface (basic), database caching |
| **v0.4** | Week 5-6 | Email alerts, Docker, unit tests |
| **v1.0** | Month 2 | Feature complete, production ready |
| **v1.5** | Month 3 | Web API, advanced analytics |
| **v2.0** | Month 4+ | Platform expansion, ML features |

---

## Getting Involved

### For Contributors
1. Review issues and pick a task
2. Follow Python style guide (PEP 8)
3. Add tests for new features
4. Create pull requests with clear descriptions

### For Users
1. Report bugs with reproduction steps
2. Suggest new features via GitHub issues
3. Vote on feature requests
4. Help with documentation/translations

---

## Dependencies to Monitor

- **Playwright** - Dynamic scraping, may break with FB/HiFiShark DOM changes
- **BeautifulSoup4** - HTML parsing, stable
- **Requests** - HTTP library, stable
- **Python 3.7+** - Minimum requirement, consider 3.10+ for future

---

## Notes

- Scraper reliability depends on target sites not blocking automated access
- Regular maintenance needed as websites update their structure
- Performance scales with number of active scrapers and result size
- Consider ethical guidelines (rate limiting, user agents, robots.txt)
