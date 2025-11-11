#!/usr/bin/env python3
"""
Audio Search - Multi-scraper search tool for audio equipment
Searches across multiple marketplaces: Blocket, Tradera, Facebook, HiFiShark, HifiTorget
"""

import argparse
import asyncio
import sys
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

from Scrapers import (
    BlocketScraper,
    TraderaScraper,
    FacebookScraper,
    HifiTorgetScraper,
    HiFiSharkScraper,
    ReferenceAudioScraper,
    LjudmakarnScraper,
    HiFiPunktenScraper,
    RehifiScraper,
    AudioPerformanceScraper,
    HifiExperienceScraper,
    AudioConceptScraper,
    LassesHiFiScraper,
    AkkelisAudioScraper,
    HifiPulsScraper,
)
from base import ListingResult
from utils import normalize_date
from search_utils import expand_search_term


class AudioSearch:
    """Main orchestrator for running multiple scrapers"""

    def __init__(self, include_sites: Optional[List[str]] = None, exclude_sites: Optional[List[str]] = None):
        # All available scrapers
        all_scrapers = {
            'Blocket': BlocketScraper(),
            'Tradera': TraderaScraper(),
            'Facebook Marketplace': FacebookScraper(),
            'HifiTorget': HifiTorgetScraper(),
            'HiFiShark': HiFiSharkScraper(),
            'Reference Audio': ReferenceAudioScraper(),
            'Ljudmakarn': LjudmakarnScraper(),
            'HiFi-Punkten': HiFiPunktenScraper(),
            'Rehifi': RehifiScraper(),
            'AudioPerformance': AudioPerformanceScraper(),
            'HiFi Experience': HifiExperienceScraper(),
            'AudioConcept': AudioConceptScraper(),
            'Lasses HiFi': LassesHiFiScraper(),
            'Akkelis Audio': AkkelisAudioScraper(),
            'HiFi Puls': HifiPulsScraper(),
        }

        def match_site_name(user_input: str, scraper_name: str) -> bool:
            """Check if user input matches scraper name (case-insensitive, supports partial match)"""
            user_lower = user_input.lower()
            scraper_lower = scraper_name.lower()
            # Exact match or partial match (e.g., "facebook" matches "Facebook Marketplace")
            return user_lower == scraper_lower or user_lower in scraper_lower.split()

        # Filter scrapers based on include/exclude options
        if include_sites:
            # Only include specified sites (case-insensitive matching with partial support)
            self.scrapers = []
            for site in include_sites:
                matched = False
                for name, scraper in all_scrapers.items():
                    if match_site_name(site, name) and scraper not in self.scrapers:
                        self.scrapers.append(scraper)
                        matched = True
                        break
                if not matched:
                    from colors import warning
                    print(f"{warning('Warning:')} Unrecognized site '{site}' (available: {', '.join(all_scrapers.keys())})", file=sys.stderr)
        elif exclude_sites:
            # Exclude specified sites (case-insensitive matching with partial support)
            excluded_scrapers = set()
            for site in exclude_sites:
                matched = False
                for name, scraper in all_scrapers.items():
                    if match_site_name(site, name):
                        excluded_scrapers.add(scraper)
                        matched = True
                        break
                if not matched:
                    from colors import warning
                    print(f"{warning('Warning:')} Unrecognized site '{site}' (available: {', '.join(all_scrapers.keys())})", file=sys.stderr)
            self.scrapers = [s for s in all_scrapers.values() if s not in excluded_scrapers]
        else:
            # All scrapers enabled by default
            self.scrapers = list(all_scrapers.values())

        self.browser_scrapers = [FacebookScraper, TraderaScraper, BlocketScraper, HiFiSharkScraper]

    async def search_all(self, query: str) -> Dict[str, List[ListingResult]]:
        """Search all enabled scrapers for a given query"""
        results = {}

        if not query or not query.strip():
            from colors import warning
            print(f"{warning('Warning:')} Empty search query provided", file=sys.stderr)
            return results

        from colors import info
        print(f"\n{info('DEBUG:')} Starting search for query: '{query}'", file=sys.stderr)
        print(f"{info('DEBUG:')} Enabled scrapers: {[s.name for s in self.scrapers]}", file=sys.stderr)

        # Create tasks for all enabled scrapers
        tasks = []
        for scraper in self.scrapers:
            print(f"{info('DEBUG:')} Creating search task for {scraper.name}", file=sys.stderr)
            task = asyncio.create_task(self._search_scraper(scraper, query.strip()))
            tasks.append((scraper.name, task))

        # Wait for all tasks to complete with timeout
        for name, task in tasks:
            try:
                print(f"{info('DEBUG:')} Waiting for {name} results...", file=sys.stderr)
                scraper_results = await asyncio.wait_for(task, timeout=60.0)
                results[name] = scraper_results
                print(f"{info('DEBUG:')} {name} returned {len(scraper_results)} results", file=sys.stderr)
            except asyncio.TimeoutError:
                from colors import warning
                print(f"{warning(f'Timeout:')} {name} search timed out after 60 seconds", file=sys.stderr)
                results[name] = []
            except Exception as e:
                from colors import error
                error_type = type(e).__name__
                print(f"{error(f'Error in {name}:')} {error_type}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                results[name] = []

        return results
    
    async def _search_scraper(self, scraper, query: str) -> List[ListingResult]:
        """Search a single scraper with error handling"""
        try:
            # Validate query
            if not query or not query.strip():
                return []
            
            return await scraper.search(query)
        except KeyboardInterrupt:
            raise  # Re-raise keyboard interrupt
        except Exception as e:
            from colors import error
            error_type = type(e).__name__
            print(f"{error(f'Error searching {scraper.name}:')} {error_type}: {e}", file=sys.stderr)
            return []
    
    async def close_all(self):
        """Close all browser resources properly"""
        # Close browsers first, before event loop closes
        for scraper in self.scrapers:
            if hasattr(scraper, 'close'):
                try:
                    # Use a timeout to ensure cleanup completes
                    await asyncio.wait_for(scraper.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    # If cleanup times out, try to force close
                    if hasattr(scraper, 'browser') and scraper.browser:
                        try:
                            await scraper.browser.close()
                        except:
                            pass
                except Exception as e:
                    # Suppress cleanup warnings - they're harmless and happen during shutdown
                    error_msg = str(e).lower()
                    if not any(suppress in error_msg for suppress in [
                        "event loop is closed", "closed", "already closed", 
                        "cancelled", "task was destroyed"
                    ]):
                        from colors import error
                        print(f"{error(f'Error closing {scraper.name}:')} {e}", file=sys.stderr)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    Handles various formats:
    - Relative: "2 days ago", "1 hour ago", "just now", "Igår" (yesterday), "Idag" (today)
    - Absolute: "2024-10-15", "22 sep.", "Oct 17, 2025", "17/10/2025"
    - Swedish: "Idag", "Igår", "22 sep.", "17 okt"
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    now = datetime.now()
    
    # Relative dates
    if "just now" in date_str.lower() or "nu" in date_str.lower():
        return now
    
    # Swedish: "Idag" (today), "Igår" (yesterday)
    if "idag" in date_str.lower() or "today" in date_str.lower():
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    if "igår" in date_str.lower() or "yesterday" in date_str.lower():
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Relative: "X days ago", "X hours ago", "X weeks ago"
    days_ago_match = re.search(r'(\d+)\s+(day|days?)\s+ago', date_str, re.I)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    hours_ago_match = re.search(r'(\d+)\s+(hour|hours?)\s+ago', date_str, re.I)
    if hours_ago_match:
        hours = int(hours_ago_match.group(1))
        return now - timedelta(hours=hours)
    
    weeks_ago_match = re.search(r'(\d+)\s+(week|weeks?)\s+ago', date_str, re.I)
    if weeks_ago_match:
        weeks = int(weeks_ago_match.group(1))
        return (now - timedelta(weeks=weeks)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Absolute dates
    # ISO format: "2024-10-15"
    iso_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if iso_match:
        try:
            year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            return datetime(year, month, day)
        except ValueError:
            pass

    # Format: "Oct 26, 2025" or "Nov 10, 2025" (English month first format from HiFiShark)
    # Swedish month names
    swedish_months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'maj': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12
    }
    # English month names
    english_months = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    # Pattern: "MMM DD, YYYY" (month first - HiFiShark format)
    month_first_pattern = re.search(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})', date_str)
    if month_first_pattern:
        try:
            month_str = month_first_pattern.group(1).lower()
            day = int(month_first_pattern.group(2))
            year = int(month_first_pattern.group(3))

            month = english_months.get(month_str) or swedish_months.get(month_str)
            if month:
                return datetime(year, month, day)
        except (ValueError, AttributeError):
            pass

    # Pattern: "DD MMM" or "DD MMM, YYYY" (day first - traditional format)
    date_pattern = re.search(r'(\d{1,2})\s+([a-z]{3})\.?\s*(?:,?\s*(\d{4}))?', date_str, re.I)
    if date_pattern:
        try:
            day = int(date_pattern.group(1))
            month_str = date_pattern.group(2).lower()[:3]
            year_str = date_pattern.group(3)
            
            # Try Swedish months first
            month = swedish_months.get(month_str) or english_months.get(month_str)
            if month:
                year = int(year_str) if year_str else now.year
                # If no year and date is in future, assume previous year
                if not year_str and datetime(year, month, day) > now:
                    year = now.year - 1
                return datetime(year, month, day)
        except (ValueError, AttributeError):
            pass
    
    # Format: "DD/MM/YYYY" or "DD-MM-YYYY"
    slash_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str)
    if slash_match:
        try:
            day = int(slash_match.group(1))
            month = int(slash_match.group(2))
            year = int(slash_match.group(3))
            if year < 100:
                year += 2000  # Assume 20XX
            return datetime(year, month, day)
        except ValueError:
            pass
    
    # If we can't parse it, return None
    return None


def filter_by_days(results: Dict[str, List[ListingResult]], days_back: int) -> Dict[str, List[ListingResult]]:
    """
    Filter listings to only show those from the last N days.
    Listings without a date are kept (assumed to be recent).
    """
    if days_back <= 0:
        return results
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    filtered_results = {}
    
    for scraper_name, listings in results.items():
        filtered_listings = []
        for listing in listings:
            # If no date, keep it (assume it's recent)
            if not listing.posted_date:
                filtered_listings.append(listing)
                continue
            
            # Parse the date
            listing_date = parse_date(listing.posted_date)
            if listing_date is None:
                # Can't parse date, keep it (better to show than hide)
                filtered_listings.append(listing)
                continue
            
            # Keep if within the date range
            if listing_date >= cutoff_date:
                filtered_listings.append(listing)
        
        filtered_results[scraper_name] = filtered_listings
    
    return filtered_results


def format_results(results: Dict[str, List[ListingResult]], search_term: str, days_filter: Optional[int] = None, sort_by: str = 'date'):
    """Format and print search results in a clean, readable format"""
    total_results = sum(len(r) for r in results.values())

    if total_results == 0:
        print(f"\nNo results found for: '{search_term}'")
        if days_filter:
            print(f"   (Filtered to last {days_filter} days)")
        return

    # Print header
    print(f"\n{'═'*80}")
    print(f"Search Results: '{search_term}'", end="")
    if days_filter:
        print(f" (last {days_filter} days)", end="")
    print(f" [Sorted by {sort_by}]")
    print(f"{'═'*80}\n")

    # Combine all results from all scrapers into a single list with source info
    all_listings = []
    for scraper_name, listing_results in results.items():
        for listing in listing_results:
            all_listings.append((scraper_name, listing))

    # Sort based on sort_by parameter
    def get_sort_key(item):
        scraper_name, listing = item

        if sort_by == 'date':
            parsed_date = parse_date(listing.posted_date) if listing.posted_date else None
            if parsed_date:
                try:
                    date_key = -parsed_date.timestamp()  # negative for newest-first when sorting ascending
                except OSError:
                    date_key = float('-inf')
            else:
                date_key = float('inf')  # push undated items last

            source_name = scraper_name
            if scraper_name == "HiFiShark" and listing.raw_data:
                source_site = listing.raw_data.get('source_site')
                if source_site:
                    source_name = source_site

            return (0, date_key, source_name.lower())

        elif sort_by == 'site':
            # Sort by site name (alphabetical)
            return (1, scraper_name.lower())

        elif sort_by == 'price':
            # Sort by price (lowest first, None values last)
            if listing.price is None:
                return (2, float('inf'))
            try:
                price_val = float(listing.price)
                return (2, price_val)
            except (TypeError, ValueError):
                return (2, float('inf'))

    # Sort with appropriate reverse flag
    all_listings.sort(key=get_sort_key)

    def sanitize(value: Optional[str]) -> str:
        if not value:
            return "-"
        normalized = normalize_date(value)
        if normalized:
            return normalized
        return " ".join(value.split())

    def truncate(value: str, max_width: int) -> str:
        if len(value) <= max_width:
            return value
        if max_width <= 1:
            return value[:max_width]
        return value[:max_width - 1] + "…"

    column_specs = [
        ("title", "Title", 48),
        ("date", "Date", 16),
        ("price", "Price", 14),
        ("location", "Location", 20),
        ("source", "Source", 26),
    ]

    rows = []
    for idx, (scraper_name, listing) in enumerate(all_listings, 1):
        title_text = (listing.title or "").strip() or "Untitled listing"

        price_str = "-"
        if listing.price is not None:
            try:
                price_str = f"{float(listing.price):,.0f} kr"
            except (TypeError, ValueError):
                price_str = sanitize(str(listing.price))

        source = scraper_name
        if scraper_name == "HiFiShark" and listing.raw_data:
            source_site = listing.raw_data.get('source_site')
            if source_site:
                source = f"{scraper_name} ({source_site})"

        plain_title = f"{idx:3d}. {title_text}"

        rows.append({
            "idx": idx,
            "title": plain_title,
            "title_url": listing.url,
            "date": sanitize(listing.posted_date),
            "price": price_str,
            "location": sanitize(listing.location),
            "source": sanitize(source),
        })

    # Determine column widths (capped) so table stays readable
    col_widths = {}
    for key, label, cap in column_specs:
        values = [row[key] for row in rows] or [label]
        longest = max(len(value) for value in values)
        col_widths[key] = max(len(label), min(longest, cap))

    # Print header row (Title first as requested)
    header_parts = []
    for key, label, _ in column_specs:
        header_parts.append(f"{label:<{col_widths[key]}}")
    header_line = "  ".join(header_parts)
    print(header_line)
    print("-" * len(header_line))

    # Display aligned rows
    for row in rows:
        line_parts = []
        for key, _, _ in column_specs:
            if key == "title":
                display_value = truncate(row[key], col_widths[key])
                if row.get("title_url"):
                    clickable = f"\x1b]8;;{row['title_url']}\x1b\\{display_value}\x1b]8;;\x1b\\"
                else:
                    clickable = display_value
                padding = max(col_widths[key] - len(display_value), 0)
                cell = f"{clickable}{' ' * padding}"
            else:
                value = truncate(row[key], col_widths[key])
                cell = f"{value:<{col_widths[key]}}"
            line_parts.append(cell)
        print("  ".join(line_parts))

    print(f"{'═'*80}")
    print(f"Total: {total_results} result{'s' if total_results != 1 else ''} found across all scrapers")
    print(f"{'═'*80}\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="""
╔═══════════════════════════════════════════════════════════════════════╗
║  Audio Search - Multi-Marketplace Audio Equipment Scraper            ║
╚═══════════════════════════════════════════════════════════════════════╝

Search for audio equipment across multiple Swedish and international marketplaces:
  • Blocket.se (Swedish classifieds)
  • Tradera.com (Swedish auctions)
  • Facebook Marketplace (Stockholm region)
  • HifiTorget.se (Swedish HiFi marketplace)
  • HiFiShark.com (International HiFi marketplace - Sweden filter)

Results are displayed sorted by date (newest first) across all sources.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Basic search:
    %(prog)s -s "yamaha receiver"
    %(prog)s -s "hegel h90"

  Search with date filter (only show listings from last N days):
    %(prog)s -s "speakers" -d 7          # Last 7 days
    %(prog)s -s "amplifier" -d 3         # Last 3 days
    %(prog)s -s "turntable" -d 14        # Last 2 weeks

  Include only specific sites:
    %(prog)s -s "amplifier" -i Blocket                    # Only Blocket
    %(prog)s -s "speakers" -i Blocket -i Tradera          # Only Blocket and Tradera
    %(prog)s -s "hegel" -i HifiTorget -d 7                # Only HifiTorget, last 7 days

  Exclude specific sites:
    %(prog)s -s "turntable" -e Facebook                   # All except Facebook
    %(prog)s -s "receiver" -e Tradera -e Facebook         # All except Tradera and Facebook
    %(prog)s -s "amplifier" -e Blocket -d 3               # All except Blocket, last 3 days

  Multiple search terms (run separate searches):
    %(prog)s -s "speakers" -s "amplifier" -s "turntable"
    %(prog)s -s "hegel" -s "yamaha" -d 5

  Sort results:
    %(prog)s -s "amplifier" --sort date                # Sort by date (newest first) - default
    %(prog)s -s "speakers" --sort site                 # Sort by site name (alphabetical)
    %(prog)s -s "receiver" --sort price                # Sort by price (lowest first)

Available sites (case-insensitive):
  - Blocket           (Swedish classifieds)
  - Tradera           (Swedish auctions)
  - Facebook          (Facebook Marketplace Stockholm)
  - HifiTorget        (Swedish HiFi marketplace)
  - HiFiShark         (International HiFi marketplace - Sweden only)
  - Reference Audio   (Swedish retailer - Begagnat)
  - Ljudmakarn        (Stockholm retailer - Fyndhörnan)
  - HiFi-Punkten      (Retailer listings)
  - Rehifi            (Refurbished HiFi)
  - AudioPerformance  (Starweb storefront)
  - HiFi Puls         (PrestaShop demo/begagnat)
  - HiFi Experience   (WooCommerce storefront)
  - AudioConcept      (WooCommerce demo/begagnat)
  - Lasses HiFi       (Shopify collection)
  - Akkelis Audio     (Fyndhörnan specials)

Notes:
  - Results are sorted by posting date (newest first) across all marketplaces
  - Listings without dates are shown at the end
  - Use -d/--days to filter recent listings only
  - Use -i/--include to search only specific sites (can use multiple -i)
  - Use -e/--exclude to skip specific sites (can use multiple -e)
  - Cannot use -i and -e together
  - URLs are clickable in most modern terminals
  - Press Ctrl+C to cancel a running search

For more information, visit: https://github.com/yourusername/HIFI_Scrapers_Terminal
        """
    )

    parser.add_argument(
        '-s', '--search',
        action='append',
        dest='search_terms',
        required=True,
        metavar='TERM',
        help='Search term to look for (can be used multiple times for separate searches)'
    )

    parser.add_argument(
        '-d', '--days',
        type=int,
        dest='days_back',
        default=None,
        metavar='N',
        help='Only show listings from the last N days (e.g., -d 5 shows last 5 days only)'
    )

    parser.add_argument(
        '-i', '--include',
        action='append',
        dest='include_sites',
        default=None,
        metavar='SITE',
        help='Include only specific site(s). Can be: Blocket, Tradera, Facebook, HifiTorget, HiFiShark (case-insensitive, can use multiple -i)'
    )

    parser.add_argument(
        '-e', '--exclude',
        action='append',
        dest='exclude_sites',
        default=None,
        metavar='SITE',
        help='Exclude specific site(s). Can be: Blocket, Tradera, Facebook, HifiTorget, HiFiShark (case-insensitive, can use multiple -e)'
    )

    parser.add_argument(
        '--sort',
        type=str,
        dest='sort_by',
        default='date',
        choices=['date', 'site', 'price'],
        metavar='FIELD',
        help='Sort results by: date (newest first), site (alphabetical), or price (lowest first). Default: date'
    )

    args = parser.parse_args()

    # Validate that include and exclude are not used together
    if args.include_sites and args.exclude_sites:
        parser.error("Cannot use both --include and --exclude options together")
    
    if not args.search_terms:
        parser.error("At least one search term (-s) is required")

    searcher = AudioSearch(include_sites=args.include_sites, exclude_sites=args.exclude_sites)

    try:
        # Process each search term
        for search_term in args.search_terms:
            try:
                variants = expand_search_term(search_term)
                if len(variants) > 1:
                    from colors import info
                    print(f"{info('DEBUG:')} Expanding '{search_term}' to synonyms {variants}", file=sys.stderr)

                aggregated_results = {}
                seen_signatures = set()
                for variant in variants:
                    results = await searcher.search_all(variant)
                    for site, listings in results.items():
                        bucket = aggregated_results.setdefault(site, [])
                        for listing in listings:
                            signature = listing.url or f"{listing.title}|{listing.price}|{listing.location}"
                            if signature in seen_signatures:
                                continue
                            seen_signatures.add(signature)
                            bucket.append(listing)

                if args.days_back:
                    aggregated_results = filter_by_days(aggregated_results, args.days_back)

                format_results(aggregated_results, search_term, args.days_back, args.sort_by)
            except Exception as e:
                from colors import error
                print(f"{error(f'Error processing search term \"{search_term}\":')} {e}", file=sys.stderr)
                continue
    
    except KeyboardInterrupt:
        from colors import error
        print(f"\n\n{error('Search interrupted by user.')}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        from colors import error
        print(f"{error('Fatal error:')} {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Ensure cleanup happens before event loop closes
        try:
            await asyncio.wait_for(searcher.close_all(), timeout=10.0)
        except asyncio.TimeoutError:
            pass  # Timeout is okay during shutdown
        except Exception:
            pass  # Ignore cleanup errors during shutdown


if __name__ == '__main__':
    asyncio.run(main())
