from typing import List, Optional
from bs4 import BeautifulSoup
from base import BaseScraper, ListingResult
from colors import error, info, warning
from playwright.async_api import async_playwright, Browser, TimeoutError as PlaywrightTimeoutError
import re
from urllib.parse import quote_plus
import sys


class HifiTorgetScraper(BaseScraper):
    """Scraper for HifiTorget.se (Swedish hifi marketplace) - Uses Playwright for JavaScript rendering"""

    def __init__(self):
        super().__init__("https://www.hifitorget.se", "HifiTorget")
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _get_browser(self) -> Browser:
        """Get or create Playwright browser instance"""
        if self.browser is None:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
            except Exception as e:
                print(f"{error(f'Error initializing browser for {self.name}:')} {e}", file=sys.stderr)
                raise
        return self.browser

    async def close(self):
        """Clean up browser resources"""
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception as e:
            if "Event loop is closed" not in str(e) and "closed" not in str(e).lower():
                print(f"{error(f'Error closing {self.name}:')} {e}", file=sys.stderr)
    
    async def search(self, query: str, min_price: Optional[float] = None,
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """Search HifiTorget for listings using Playwright"""
        results = []

        print(f"{info('DEBUG HifiTorget:')} Starting search for '{query}'", file=sys.stderr)

        browser = await self._get_browser()
        page = await browser.new_page()

        try:
            # Try multiple search URL patterns
            # Based on actual HTML source, the correct pattern is /?q=nad
            url_patterns = [
                f"{self.base_url}/?q={quote_plus(query)}",  # Main search pattern (confirmed working)
                f"{self.base_url}?q={quote_plus(query)}",  # Without trailing slash
                f"{self.base_url}/annonser?q={quote_plus(query)}",
                f"{self.base_url}/annonser",  # Fallback: just browse all ads
            ]

            response = None
            search_url = None

            for url in url_patterns:
                print(f"{info('DEBUG HifiTorget:')} Trying URL: {url}", file=sys.stderr)
                try:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                    try:
                        # Best-effort wait for quieter network to let dynamic content settle
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except PlaywrightTimeoutError:
                        print(f"{warning('DEBUG HifiTorget:')} networkidle state not reached for {url} within 5s, continuing with current content", file=sys.stderr)

                    status = response.status if response else 'unknown'
                    print(f"{info('DEBUG HifiTorget:')} Response status: {status}", file=sys.stderr)

                    # If we get 200 (success) or 304 (not modified), use this URL
                    if response and response.status in [200, 304]:
                        search_url = url
                        print(f"{info('DEBUG HifiTorget:')} Success! Using URL: {url}", file=sys.stderr)
                        break
                except PlaywrightTimeoutError as e:
                    print(f"{warning('DEBUG HifiTorget:')} Timeout waiting for {url}: {e}", file=sys.stderr)
                    continue
                except Exception as e:
                    print(f"{warning('DEBUG HifiTorget:')} Failed with {url}: {e}", file=sys.stderr)
                    continue

            if not search_url or not response or response.status not in [200, 304]:
                print(f"{error('DEBUG HifiTorget:')} All URL patterns failed", file=sys.stderr)
                return results

            print(f"{info('DEBUG HifiTorget:')} Page loaded successfully", file=sys.stderr)

            # Wait a bit for JavaScript to render
            await page.wait_for_timeout(3000)

            # Get the page content
            html_content = await page.content()
            print(f"{info('DEBUG HifiTorget:')} Page content length: {len(html_content)} chars", file=sys.stderr)

            # Debug: Print first 2000 chars of HTML
            print(f"{info('DEBUG HifiTorget:')} HTML preview (first 2000 chars):", file=sys.stderr)
            print(html_content[:2000], file=sys.stderr)
            print(f"{info('DEBUG HifiTorget:')} --- End HTML preview ---", file=sys.stderr)

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Try multiple selector strategies for finding listings
            listings = self._find_listings(soup)

            print(f"{info('DEBUG HifiTorget:')} Found {len(listings)} potential listing elements", file=sys.stderr)

            for idx, listing in enumerate(listings, 1):
                try:
                    print(f"{info('DEBUG HifiTorget:')} Parsing listing {idx}/{len(listings)}", file=sys.stderr)
                    listing_data = self._parse_listing(listing)
                    if listing_data:
                        print(f"{info('DEBUG HifiTorget:')} Successfully parsed: {listing_data.title[:50]}...", file=sys.stderr)
                        results.append(listing_data)
                    else:
                        print(f"{warning('DEBUG HifiTorget:')} Listing {idx} returned no data", file=sys.stderr)
                except Exception as e:
                    print(f"{error('Error parsing HifiTorget listing:')} {e}", file=sys.stderr)
                    import traceback
                    traceback.print_exc()
                    continue

        except Exception as e:
            print(f"{error('Error during HifiTorget search:')} {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        finally:
            await page.close()

        print(f"{info('DEBUG HifiTorget:')} Returning {len(results)} valid results", file=sys.stderr)
        return results
    
    def _find_listings(self, soup: BeautifulSoup) -> List:
        """Find listing elements using multiple strategies"""
        from colors import info, warning
        import sys

        listings = []

        print(f"{info('DEBUG HifiTorget:')} Strategy 1 - Looking for common listing containers", file=sys.stderr)

        # Strategy 1: Look for HifiTorget-specific card containers
        # Based on actual HTML: <div class="card mb-3" style="max-width: 840px; border-color: #ffffff">
        selectors = [
            ('div', {'class': 'card mb-3'}),  # Exact match for HifiTorget cards
            ('div', {'class': re.compile(r'card.*mb-', re.I)}),  # Flexible card match
            ('article', {'class': re.compile(r'listing|item|annons|ad', re.I)}),
            ('div', {'class': re.compile(r'listing|item|annons|ad|product', re.I)}),
            ('a', {'href': re.compile(r'/visa_annons|/annons|/produkt', re.I)}),  # HifiTorget uses /visa_annons.php
        ]

        for tag, attrs in selectors:
            found = soup.find_all(tag, attrs)
            if found:
                print(f"{info('DEBUG HifiTorget:')} Found {len(found)} elements with selector: {tag} {attrs}", file=sys.stderr)
                listings.extend(found)
                break
            else:
                print(f"{info('DEBUG HifiTorget:')} No matches for selector: {tag} {attrs}", file=sys.stderr)

        # Strategy 2: Look for links that contain listing patterns in href
        if not listings:
            print(f"{info('DEBUG HifiTorget:')} Strategy 2 - Looking for listing links", file=sys.stderr)
            listing_links = soup.find_all('a', href=re.compile(r'/annons|/produkt|/item|/listing', re.I))
            print(f"{info('DEBUG HifiTorget:')} Found {len(listing_links)} listing links", file=sys.stderr)
            for link in listing_links:
                # Find parent container
                parent = link.find_parent(['article', 'div', 'li'])
                if parent and parent not in listings:
                    listings.append(parent)
            print(f"{info('DEBUG HifiTorget:')} Extracted {len(listings)} unique parent containers", file=sys.stderr)

        # Strategy 3: Generic fallback - look for elements with price indicators
        if not listings:
            print(f"{info('DEBUG HifiTorget:')} Strategy 3 - Looking for price indicators", file=sys.stderr)
            price_elements = soup.find_all(string=re.compile(r'\d+\s*kr', re.I))
            print(f"{info('DEBUG HifiTorget:')} Found {len(price_elements)} price indicators", file=sys.stderr)
            for price_elem in price_elements:
                parent = price_elem.find_parent(['article', 'div', 'li', 'a'])
                if parent and parent not in listings:
                    listings.append(parent)
            print(f"{info('DEBUG HifiTorget:')} Extracted {len(listings)} unique elements with prices", file=sys.stderr)

        result_count = min(len(listings), 50)
        print(f"{info('DEBUG HifiTorget:')} Returning {result_count} listings (limited from {len(listings)} found)", file=sys.stderr)
        return listings[:50]  # Limit to first 50 to avoid duplicates
    
    def _parse_listing(self, listing_element) -> Optional[ListingResult]:
        """Parse a single listing element"""
        # Find title and link - try multiple strategies
        title = None
        url = None
        
        # Strategy 1: Look for title in meaningful link text (skip empty anchors like image wrappers)
        for link in listing_element.find_all('a', href=True):
            text = link.get_text(strip=True)
            if text and len(text) > 2:
                title = text
                url = self._normalize_url(link['href'])
                break
        
        # Strategy 2: Look for heading with title
        if not title:
            heading = listing_element.find(['h1', 'h2', 'h3', 'h4'])
            if heading:
                title = heading.get_text(strip=True)
                # Try to find link in heading or parent
                link = heading.find('a', href=True) or listing_element.find('a', href=True)
                if link:
                    url = self._normalize_url(link['href'])
        
        # Strategy 3: Use data attributes or class names
        if not title:
            title_elem = listing_element.find(class_=re.compile(r'title|heading|name', re.I))
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        if not title:
            return None
        
        if not url:
            # Try to construct URL from title or use base URL
            url = self.base_url
        
        # Find price - try multiple strategies
        price = None
        
        # Look for price text containing "kr" or numbers
        price_text_elem = listing_element.find(string=re.compile(r'\d+[\s.,]*\d*\s*(kr|sek|€)', re.I))
        if price_text_elem:
            price = self._extract_price(price_text_elem)
        
        if not price:
            # Look for price in class names
            price_elem = listing_element.find(class_=re.compile(r'price|pris|cost', re.I))
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price = self._extract_price(price_text)
        
        if not price:
            # Look for any element with price-like patterns
            price_candidates = listing_element.find_all(string=re.compile(r'\d{3,}', re.I))
            for candidate in price_candidates:
                # Check if surrounded by price context
                try:
                    parent = candidate.find_parent()
                    parent_text = parent.get_text() if parent else str(candidate)
                except (AttributeError, TypeError):
                    parent_text = str(candidate)
                
                if 'kr' in parent_text.lower() or 'pris' in parent_text.lower():
                    price = self._extract_price(str(candidate))
                    if price:
                        break
        
        # Find image - try multiple strategies
        image_url = None
        img = listing_element.find('img')
        if img:
            image_url = (img.get('src') or 
                        img.get('data-src') or 
                        img.get('data-lazy-src') or
                        img.get('data-original'))
            if image_url:
                image_url = self._normalize_url(image_url)
        
        # Find description
        description = None
        desc_elem = listing_element.find(class_=re.compile(r'description|text|beskrivning|excerpt', re.I))
        if desc_elem:
            description = desc_elem.get_text(strip=True)
        else:
            # Try to get text content excluding title
            all_text = listing_element.get_text(strip=True)
            if all_text and title:
                # Remove title from description
                description = all_text.replace(title, '', 1).strip()
                if len(description) > 500:
                    description = description[:500] + '...'
        
        # Find posted date
        posted_date = None
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
            r'\d+\s+\w+\s+\d{4}',
        ]
        month_pattern = r'(?:jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)'
        date_patterns.append(rf'\b\d{{1,2}}\s+{month_pattern}(?:\s+\d{{2,4}})?')

        for pattern in date_patterns:
            date_elem = listing_element.find(string=re.compile(pattern, re.I))
            if date_elem:
                posted_date = date_elem.strip()
                break

        if not posted_date:
            relative_elem = listing_element.find(string=re.compile(r'(idag|igår|\d{1,2}:\d{2})', re.I))
            if relative_elem:
                posted_date = relative_elem.strip()
            else:
                date_elem = listing_element.find(class_=re.compile(r'date|datum|time|posted|inlagd', re.I))
                if date_elem:
                    posted_date = date_elem.get_text(strip=True)

        if not posted_date and url and url != self.base_url:
            posted_date = self._fetch_inlagd_date(url)
        
        # Find location - HifiTorget is Swedish, so look for Swedish cities
        location = None
        listing_text = listing_element.get_text(separator='\n', strip=True)
        
        # Look for Swedish cities
        swedish_cities = [
            'Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Västerås', 'Örebro',
            'Linköping', 'Helsingborg', 'Jönköping', 'Norrköping', 'Lund',
            'Umeå', 'Gävle', 'Borås', 'Eskilstuna', 'Södertälje', 'Karlstad',
            'Växjö', 'Halmstad', 'Sundsvall', 'Luleå', 'Trollhättan', 'Östersund'
        ]
        for city in swedish_cities:
            city_pattern = re.compile(rf'\b{city}\b', re.I)
            if city_pattern.search(listing_text):
                location = city
                break
        
        # Also look for location patterns
        if not location:
            location_pattern = re.compile(r'(?:Plats|Stad|Location|Från)[:\s]+([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*)', re.I)
            match = location_pattern.search(listing_text)
            if match:
                location = match.group(1).strip()
        
        # As a final fallback, grab the first <small> element that looks like a city/region label
        if not location:
            for elem in listing_element.find_all('small'):
                text = elem.get_text(strip=True)
                if text and not re.search(r'\d', text) and len(text) > 3:
                    if ',' in text or any(city.lower() in text.lower() for city in swedish_cities):
                        location = text
                        break
        
        raw_data = {
            'html': str(listing_element)[:1000],  # Store first 1000 chars for debugging
            'title_source': 'found' if title else 'missing',
            'price_source': 'found' if price else 'missing',
        }
        
        return ListingResult(
            title=title,
            description=description,
            price=price,
            url=url,
            image_url=image_url,
            posted_date=posted_date,
            location=location,
            raw_data=raw_data
        )

    def _fetch_inlagd_date(self, url: str) -> Optional[str]:
        """Fetch the listing detail page to extract the 'Inlagd' timestamp"""
        try:
            soup = self._fetch_page(url)
            if not soup:
                return None

            # Look for text nodes that include "Inlagd"
            inlagd_elem = soup.find(string=re.compile(r'Inlagd', re.I))
            if inlagd_elem:
                text = inlagd_elem
                if hasattr(inlagd_elem, 'parent'):
                    text = inlagd_elem.parent.get_text(" ", strip=True)
                cleaned = re.sub(r'Inlagd[:\s]*', '', text, flags=re.I).strip()
                return cleaned or None

            # Fallback: look for elements with class names
            container = soup.find(class_=re.compile(r'inlagd|date|datum', re.I))
            if container:
                text = container.get_text(" ", strip=True)
                cleaned = re.sub(r'Inlagd[:\s]*', '', text, flags=re.I).strip()
                return cleaned or None
        except Exception as e:
            print(f"{warning('DEBUG HifiTorget:')} Failed to fetch detail page for date: {e}", file=sys.stderr)
        return None
