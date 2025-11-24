from typing import List, Optional
from playwright.async_api import async_playwright, Browser, Page
from base import BaseScraper, ListingResult
from colors import error, info, warning, success
from datetime import datetime
import sys
from debug_utils import debug_print


class HiFiSharkScraper(BaseScraper):
    """Scraper for HiFiShark.com using Playwright for JavaScript-heavy content"""

    def __init__(self):
        super().__init__("https://www.hifishark.com", "HiFiShark")
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _get_browser(self) -> Browser:
        """Get or create browser instance"""
        if not self.browser:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
            except Exception as e:
                print(f"{error(f'Error initializing browser for {self.name}:')} {e}", file=sys.stderr)
                raise
        return self.browser

    async def search(self, query: str, min_price: Optional[float] = None,
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """
        Search HiFiShark with Sweden filter

        Args:
            query: Search query string
            min_price: Minimum price filter (optional)
            max_price: Maximum price filter (optional)
            **kwargs: Additional parameters

        Returns:
            List of ListingResult objects filtered to Sweden only
        """
        results = []

        try:
            browser = await self._get_browser()
            page = await browser.new_page()

            try:
                # Build search URL with Sweden country filter
                # The correct URL parameter is country_iso=SE (not country or country[])
                search_url = f"{self.base_url}/search"
                params = [
                    f"q={query}",
                    "country_iso=SE",  # Filter for Sweden only
                ]

                # Add price filters if provided
                if min_price:
                    params.append(f"minPrice={int(min_price)}")
                if max_price:
                    params.append(f"maxPrice={int(max_price)}")

                full_url = f"{search_url}?{'&'.join(params)}"

                debug_print(f"{self.name}: Navigating to {full_url}", info)

                # Navigate and wait for network to be idle
                await page.goto(full_url, wait_until='networkidle', timeout=60000)

                # Wait for JavaScript to populate search results
                await page.wait_for_timeout(3000)

                # Extract search results from JavaScript object
                search_data = await page.evaluate("""
                    () => {
                        if (typeof searchResults !== 'undefined') {
                            return searchResults;
                        }
                        return null;
                    }
                """)
                search_info = await page.evaluate("""
                    () => {
                        if (typeof searchInfo !== 'undefined') {
                            return searchInfo;
                        }
                        return null;
                    }
                """)

                if not search_data:
                    print(f"{warning(f'{self.name}:')} No search results data found", file=sys.stderr)
                    return results

                # Check if we have hits
                if not isinstance(search_data, dict) or 'hits' not in search_data:
                    print(f"{warning(f'{self.name}:')} Unexpected search data structure", file=sys.stderr)
                    return results

                hits = search_data.get('hits', [])
                total = search_data.get('total', 0)

                debug_print(f"{self.name}: Found {len(hits)} results (total: {total}), filtering for Sweden...", info)

                if total > len(hits):
                    if not search_info:
                        print(f"{warning(f'{self.name}:')} Unable to fetch additional pages (missing searchInfo)", file=sys.stderr)
                    else:
                        debug_print(f"{self.name}: Need pagination - fetching {total - len(hits)} more hits...", info)
                        extra_hits = await self._fetch_additional_hits(page, search_info, len(hits), total)
                        if extra_hits:
                            hits.extend(extra_hits)
                            debug_print(f"{self.name}: Retrieved {len(hits)}/{total} hits after pagination", info)
                        else:
                            print(f"{warning(f'{self.name}:')} Pagination request returned no extra hits (expected {total - len(hits)} more)", file=sys.stderr)
                else:
                    debug_print(f"{self.name}: All {total} hits loaded in initial page (no pagination needed)", info)

                # Process each hit
                filtered_out = 0
                parse_errors = 0
                for hit in hits:
                    try:
                        listing = self._parse_hit(hit)
                        if listing:
                            results.append(listing)
                        else:
                            # Hit was filtered out (likely by country filter)
                            filtered_out += 1
                            location_data = hit.get('location', {})
                            country_iso = location_data.get('country_iso', '').lower()
                            debug_print(f"{self.name}: Filtered out hit with country_iso='{country_iso}'", warning)
                    except Exception as e:
                        parse_errors += 1
                        print(f"{warning(f'{self.name} parse error:')} {e}", file=sys.stderr)
                        continue

                debug_print(f"{self.name}: Successfully parsed {len(results)} listings (filtered out: {filtered_out}, errors: {parse_errors})", success)

            finally:
                await page.close()

        except Exception as e:
            print(f"{error(f'Error searching {self.name}:')} {e}", file=sys.stderr)

        return results

    async def _fetch_additional_hits(self, page: Page, search_info: dict, start_from: int, total_hits: int) -> List[dict]:
        """
        Use HiFiShark's internal /searchSlice endpoint to paginate beyond the initial 48 hits.
        """
        extra_hits: List[dict] = []
        offset = start_from

        while offset < total_hits:
            try:
                debug_print(f"{self.name}: Loading more hits ({offset}/{total_hits})", info)
                payload = {
                    "info": search_info,
                    "offset": offset,
                    "totalHits": total_hits
                }
                response = await page.evaluate("""
                    async ({ info, offset, totalHits }) => {
                        const params = new URLSearchParams();
                        const formatValue = (value) => {
                            if (value === null || typeof value === 'undefined') {
                                return '';
                            }
                            if (typeof value === 'boolean') {
                                return value ? 'true' : 'false';
                            }
                            return String(value);
                        };
                        Object.entries(info || {}).forEach(([key, value]) => {
                            params.append(`searchInfo[${key}]`, formatValue(value));
                        });
                        params.set('searchInfo[from]', String(offset));
                        if (typeof totalHits === 'number' && !Number.isNaN(totalHits)) {
                            params.set('searchInfo[totalHits]', String(totalHits));
                        }

                        const response = await fetch('/searchSlice', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                'X-Requested-With': 'XMLHttpRequest'
                            },
                            body: params.toString()
                        });

                        if (!response.ok) {
                            return { error: `HTTP ${response.status}` };
                        }

                        return await response.json();
                    }
                """, payload)
            except Exception as e:
                print(f"{error(f'{self.name}:')} Pagination request failed at offset {offset}: {e}", file=sys.stderr)
                break

            # Check for HTTP error
            if isinstance(response, dict) and 'error' in response:
                print(f"{error(f'{self.name}:')} Pagination HTTP error at offset {offset}: {response['error']}", file=sys.stderr)
                break

            if not response or 'hits' not in response:
                print(f"{error(f'{self.name}:')} Unexpected pagination response at offset {offset}: {response}", file=sys.stderr)
                break

            new_hits = response.get('hits', [])
            if not new_hits:
                debug_print(f"{self.name}: No more hits returned at offset {offset} (expected {total_hits - offset} more)", warning)
                break

            extra_hits.extend(new_hits)
            offset += len(new_hits)

            # Small delay to be polite to the remote service
            await page.wait_for_timeout(400)

        return extra_hits

    def _parse_hit(self, hit: dict) -> Optional[ListingResult]:
        """
        Parse a single hit from HiFiShark search results

        Args:
            hit: Dictionary containing listing data from searchResults.hits

        Returns:
            ListingResult object or None if parsing fails
        """
        try:
            # Extract basic fields
            description = hit.get('description', 'No description')
            title = description  # HiFiShark uses description as the main title

            # Extract price
            price = None
            price_data = hit.get('price', {})
            if price_data and isinstance(price_data, dict):
                price = price_data.get('value')

            # Use display_price which includes currency symbol
            display_price = hit.get('display_price', '')

            # Extract URL - HiFiShark uses relative URLs that redirect
            relative_url = hit.get('url', '')
            if relative_url:
                url = self._normalize_url(relative_url)
            else:
                return None

            # Extract source site name from URL
            source_site = None
            if relative_url.startswith('http://') or relative_url.startswith('https://'):
                # Direct URL - extract domain
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(relative_url)
                    source_site = parsed.netloc.replace('www.', '')
                except Exception:
                    pass
            else:
                # Redirect URL - try to extract from image_url
                image_url_raw = hit.get('image_url', '')
                if image_url_raw:
                    try:
                        from urllib.parse import urlparse
                        # Image URLs often contain the source domain
                        if 'blocket' in image_url_raw.lower():
                            source_site = 'blocket.se'
                        elif 'tradera' in image_url_raw.lower():
                            source_site = 'tradera.com'
                        elif 'hifitorget' in image_url_raw.lower():
                            source_site = 'hifitorget.se'
                        else:
                            # Try to extract from image URL
                            parsed = urlparse(image_url_raw)
                            domain = parsed.netloc.replace('www.', '')
                            if domain and not domain.startswith('hifishark'):
                                source_site = domain
                    except Exception:
                        pass

            # Extract image URL
            image_url = hit.get('image_url')

            # Extract location
            location_data = hit.get('location', {})
            country_iso = location_data.get('country_iso', '').lower()

            # Only include Sweden listings
            # Note: HiFiShark returns lowercase country codes
            if country_iso != 'se':
                return None

            location = 'Sweden'  # Could be enhanced with more specific location if available

            # Extract date
            posted_date = None
            display_date_str = hit.get('display_date_str')
            if display_date_str:
                posted_date = display_date_str
            else:
                # Try to parse display_date timestamp
                display_date = hit.get('display_date')
                if display_date:
                    try:
                        dt = datetime.fromtimestamp(display_date)
                        posted_date = dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass

            # Store raw data for debugging
            raw_data = {
                'source': 'hifishark',
                'source_site': source_site,  # Store the original source site
                'country_iso': country_iso,
                'site_id': hit.get('site_id'),
                'score': hit.get('_score'),
                'last_seen': hit.get('last_seen_str'),
            }

            return ListingResult(
                title=title.strip(),
                description=display_price if display_price else None,  # Show price as description
                price=price,
                url=url,
                image_url=image_url,
                posted_date=posted_date,
                location=location,
                raw_data=raw_data
            )

        except Exception as e:
            print(f"{error('Error parsing HiFiShark hit:')} {e}", file=sys.stderr)
            return None

    async def close(self):
        """Close browser instance and playwright"""
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            # Suppress cleanup errors - they're harmless
            if "Event loop is closed" not in str(e) and "closed" not in str(e).lower():
                print(f"{error(f'Error closing {self.name}:')} {e}", file=sys.stderr)
