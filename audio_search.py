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

from blocket import BlocketScraper
from tradera import TraderaScraper
from facebook import FacebookScraper
from hifitorget import HifiTorgetScraper
from base import ListingResult


class AudioSearch:
    """Main orchestrator for running multiple scrapers"""
    
    def __init__(self):
        # All scrapers enabled
        self.scrapers = [
            BlocketScraper(),
            TraderaScraper(),
            FacebookScraper(),
            HifiTorgetScraper(),
        ]
        self.browser_scrapers = [FacebookScraper, TraderaScraper, BlocketScraper]
    
    async def search_all(self, query: str) -> Dict[str, List[ListingResult]]:
        """Search all scrapers for a given query"""
        results = {}
        
        if not query or not query.strip():
            from colors import warning
            print(f"{warning('Warning:')} Empty search query provided", file=sys.stderr)
            return results
        
        # Create tasks for all scrapers
        tasks = []
        for scraper in self.scrapers:
            task = asyncio.create_task(self._search_scraper(scraper, query.strip()))
            tasks.append((scraper.name, task))
        
        # Wait for all tasks to complete with timeout
        for name, task in tasks:
            try:
                scraper_results = await asyncio.wait_for(task, timeout=60.0)
                results[name] = scraper_results
            except asyncio.TimeoutError:
                from colors import warning
                print(f"{warning(f'Timeout:')} {name} search timed out after 60 seconds", file=sys.stderr)
                results[name] = []
            except Exception as e:
                from colors import error
                error_type = type(e).__name__
                print(f"{error(f'Error in {name}:')} {error_type}: {e}", file=sys.stderr)
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
    
    # Format: "22 sep.", "17 okt", "Oct 17, 2025"
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
    
    # Pattern: "DD MMM" or "DD MMM, YYYY"
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


def format_url_for_terminal(url: str, title: str) -> str:
    """Format URL as clickable terminal hyperlink (if supported) or plain URL"""
    # Try terminal hyperlink format (OSC 8 escape sequence)
    # Format: \033]8;;URL\033\\TEXT\033]8;;\033\\
    return f"\033]8;;{url}\033\\{title}\033]8;;\033\\"
    # Fallback to plain URL if hyperlinks don't work:
    # return f"{title}\n  {url}"


def format_results(results: Dict[str, List[ListingResult]], search_term: str, days_filter: Optional[int] = None):
    """Format and print search results in a clean, readable format"""
    total_results = sum(len(r) for r in results.values())
    
    if total_results == 0:
        print(f"\n🔍 No results found for: '{search_term}'")
        if days_filter:
            print(f"   (Filtered to last {days_filter} days)")
        return
    
    # Print header
    print(f"\n{'═'*80}")
    print(f"🔍 Search Results: '{search_term}'", end="")
    if days_filter:
        print(f" (last {days_filter} days)")
    else:
        print()
    print(f"{'═'*80}\n")
    
    # Group results by scraper
    for scraper_name, listing_results in results.items():
        if not listing_results:
            continue
        
        print(f"\n{'─'*80}")
        print(f"📦 {scraper_name} ({len(listing_results)} result{'s' if len(listing_results) != 1 else ''})")
        print(f"{'─'*80}\n")
        
        for idx, listing in enumerate(listing_results, 1):
            # Format title with clickable URL
            title_url = format_url_for_terminal(listing.url, listing.title)
            
            # Build info line with date first (if available), then price, then location
            info_parts = []
            if listing.posted_date:
                info_parts.append(f"📅 {listing.posted_date}")
            if listing.price:
                info_parts.append(f"💰 {listing.price:,.0f} kr")
            if listing.location:
                info_parts.append(f"📍 {listing.location}")
            
            # Print result with info line
            if info_parts:
                print(f"{idx:3d}. {title_url}")
                print(f"     {' | '.join(info_parts)}")
            else:
                print(f"{idx:3d}. {title_url}")
            
            # Print description if available (truncated)
            if listing.description and len(listing.description.strip()) > 0:
                desc = listing.description.strip()
                if len(desc) > 150:
                    desc = desc[:150] + "..."
                # Wrap description to 75 chars per line
                words = desc.split()
                lines = []
                current_line = []
                for word in words:
                    if len(' '.join(current_line + [word])) <= 75:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                for line in lines:
                    print(f"     💬 {line}")
            
            # Print URL for copy-paste (less prominent)
            print(f"     🔗 {listing.url}")
            print()
    
    print(f"{'═'*80}")
    print(f"✨ Total: {total_results} result{'s' if total_results != 1 else ''} found across all scrapers")
    print(f"{'═'*80}\n")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Search for audio equipment across multiple marketplaces',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -s "yamaha receiver"
  %(prog)s -s "speakers" -s "amplifier" -s "turntable"
  %(prog)s -s "hegel" -d 5
  %(prog)s -s "amplifier" -d 7
        """
    )
    
    parser.add_argument(
        '-s', '--search',
        action='append',
        dest='search_terms',
        required=True,
        help='Search term (can be used multiple times to search for multiple terms)'
    )
    
    parser.add_argument(
        '-d', '--days',
        type=int,
        dest='days_back',
        default=None,
        metavar='N',
        help='Only show listings from the last N days (e.g., -d 5 for last 5 days)'
    )
    
    args = parser.parse_args()
    
    if not args.search_terms:
        parser.error("At least one search term (-s) is required")
    
    searcher = AudioSearch()
    
    try:
        # Process each search term
        for search_term in args.search_terms:
            try:
                results = await searcher.search_all(search_term)
                
                # Apply days filter if specified
                if args.days_back:
                    results = filter_by_days(results, args.days_back)
                
                format_results(results, search_term, args.days_back)
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
