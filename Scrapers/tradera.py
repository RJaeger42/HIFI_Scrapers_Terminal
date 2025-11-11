from typing import List, Optional
from bs4 import BeautifulSoup
from base import BaseScraper, ListingResult
from colors import error, info, warning, success
import re
import sys
from urllib.parse import quote_plus
from playwright.async_api import async_playwright, Browser


class TraderaScraper(BaseScraper):
    """Scraper for Tradera.com (Swedish auction site)"""
    
    def __init__(self):
        super().__init__("https://www.tradera.com", "Tradera")
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

    def _matches_query(self, text: Optional[str], tokens: List[str], full_query: str) -> bool:
        if not tokens:
            return True
        haystack = (text or "").lower()
        if full_query and full_query in haystack:
            return True
        for token in tokens:
            if not re.search(rf"\b{re.escape(token)}\b", haystack):
                return False
        return True

    async def search(self, query: str, min_price: Optional[float] = None,
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """Search Tradera for auctions"""
        results = []
        query = query or ""
        query_tokens = [tok for tok in re.split(r"\s+", query.lower().strip()) if tok]
        full_query = " ".join(query_tokens)
        
        # Build search URL - Tradera uses 'q' parameter, not 'query'
        search_url = f"{self.base_url}/search"
        params = {
            'q': query,
        }
        
        if min_price:
            params['minPrice'] = int(min_price)
        if max_price:
            params['maxPrice'] = int(max_price)
        
        param_string = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
        full_url = f"{search_url}?{param_string}"
        
        # Tradera is a React app, so use Playwright for dynamic content
        soup = None
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            
            await page.goto(full_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for React to render
            
            # Scroll to trigger lazy loading
            for i in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
            
            content = await page.content()
            await page.close()
            
            soup = BeautifulSoup(content, 'html.parser')
        except Exception as e:
            soup = self._fetch_page(full_url)
        
        if not soup:
            return results
        
        # Tradera is a React app - look for common React listing patterns
        # Try multiple strategies for finding listings
        listings = []
        
        # Strategy 1: Look for links with /auktion/ pattern
        listing_links = soup.find_all('a', href=re.compile(r'/auktion/', re.I))
        for link in listing_links:
            parent = link.find_parent(['article', 'div', 'li', 'section'])
            if parent and parent not in listings:
                listings.append(parent)
        
        # Strategy 1b: Look for any links that might be listings (href contains item ID pattern)
        if not listings:
            # Tradera might use different URL patterns - try to find clickable items
            clickable_items = soup.find_all('a', href=re.compile(r'/(item|product|listing|auction)/|/\d+', re.I))
            for link in clickable_items:
                href = link.get('href', '')
                # Skip navigation links
                if any(skip in href.lower() for skip in ['/search', '/login', '/register', '/help', '/about']):
                    continue
                parent = link.find_parent(['article', 'div', 'li', 'section'])
                if parent and parent not in listings:
                    listings.append(parent)
        
        # Strategy 2: Look for article/div with auction/item indicators
        if not listings:
            listings = soup.find_all('article', class_=lambda x: x and ('auction' in str(x).lower() or 'item' in str(x).lower() or 'listing' in str(x).lower()))
        
        # Strategy 3: Try data attributes
        if not listings:
            listings = soup.find_all('div', {'data-testid': re.compile(r'item|auction|listing', re.I)})
        
        # Strategy 4: Look for elements containing price patterns (kr)
        if not listings:
            price_elements = soup.find_all(string=re.compile(r'\d+.*kr', re.I))
            for price_elem in price_elements[:20]:  # Limit to avoid too many
                parent = price_elem.find_parent(['article', 'div', 'li', 'section', 'a'])
                if parent and parent not in listings:
                    # Check if it has a link to an auction
                    if parent.find('a', href=re.compile(r'/auktion/', re.I)):
                        listings.append(parent)
        
        for listing in listings:
            try:
                listing_data = self._parse_listing(listing)
                if listing_data and self._matches_query(listing_data.title, query_tokens, full_query):
                    if min_price and listing_data.price and listing_data.price < min_price:
                        continue
                    if max_price and listing_data.price and listing_data.price > max_price:
                        continue
                    results.append(listing_data)
            except Exception:
                continue
        
        return results
    
    def _parse_listing(self, listing_element) -> Optional[ListingResult]:
        """Parse a single auction listing"""
        # Find title and link - Tradera may use different URL patterns
        # Try /auktion/ first (old pattern), then try other patterns
        title_link = listing_element.find('a', href=re.compile(r'/auktion/', re.I))
        
        # If not found, try other patterns that might indicate a listing
        if not title_link:
            # Try links with item/product patterns
            title_link = listing_element.find('a', href=re.compile(r'/(item|product|listing)/|/\d+', re.I))
        
        # If still not found, try any link in the element (but skip navigation)
        if not title_link:
            all_links = listing_element.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Skip navigation links
                if any(skip in href.lower() for skip in ['/search', '/login', '/register', '/help', '/about', '/contact', '/my']):
                    continue
                # Skip if it's just a fragment or empty
                if href.startswith('#') or not href:
                    continue
                # Must look like a listing URL (contains ID or path)
                if '/' in href and (re.search(r'\d+', href) or len(href.split('/')) > 2):
                    title_link = link
                    break
        
        if not title_link:
            return None
        
        title = title_link.get_text(strip=True)
        
        # If title is too short or looks like navigation/category, try to find better title
        if not title or len(title) < 5 or title in ['...', 'Läs mer', 'Mer info', 'Se mer', 'Köp nu', 'Budgivning']:
            # Try to find title in heading tags
            heading = listing_element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if heading:
                title = heading.get_text(strip=True)
            
            # Try to find title in spans or divs with title-like classes
            if not title or len(title) < 5:
                title_elem = listing_element.find(class_=lambda x: x and ('title' in str(x).lower() or 'heading' in str(x).lower() or 'name' in str(x).lower()))
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            # Try getting first meaningful text from the element
            if not title or len(title) < 5:
                all_text = listing_element.get_text(separator=' ', strip=True)
                # Take first line that's reasonably long
                for line in all_text.split('\n'):
                    line = line.strip()
                    if line and len(line) > 10:
                        # Skip common navigation text
                        if line.lower() not in ['accessoarer', 'böcker & tidningar', 'se alla', 'filtrera', 'sortera']:
                            title = line
                            break
        
        # Filter out navigation/category text
        if not title or len(title) < 5:
            return None
        
        # Skip if it looks like navigation/category
        nav_keywords = ['accessoarer', 'böcker', 'tidningar', 'kategorier', 'filtrera', 'sortera', 'se alla', 'mer info', 'läs mer']
        if any(keyword in title.lower() for keyword in nav_keywords):
            return None
        
        url = self._normalize_url(title_link['href'])
        
        # Find current bid/price
        price_elem = listing_element.find(string=re.compile(r'\d+.*kr', re.I))
        if not price_elem:
            price_elem = listing_element.find(class_=re.compile(r'price|bid|current', re.I))
        
        price = None
        if price_elem:
            price_text = price_elem.get_text() if hasattr(price_elem, 'get_text') else str(price_elem)
            price = self._extract_price(price_text)
        
        # Find image
        image_url = None
        img = listing_element.find('img')
        if img:
            image_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if image_url:
                image_url = self._normalize_url(image_url)
        
        # Description
        desc_elem = listing_element.find(class_=re.compile(r'description|text', re.I))
        description = desc_elem.get_text(strip=True) if desc_elem else None
        
        # Find posted/end date (auction)
        posted_date = None
        
        # Try multiple strategies to find date
        # Strategy 1: Look for date strings with Swedish/English patterns
        date_patterns = [
            r'\d{1,2}\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)\.?\s+\d{2,4}',  # Swedish: "22 sep. 2024"
            r'\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s+\d{2,4}',  # English: "22 Oct 2024"
            r'(idag|today)',  # Today
            r'(igår|yesterday)',  # Yesterday
            r'\d+\s+(timmar?|hours?)\s+sedan',  # Hours ago
            r'\d+\s+(dagar?|days?)\s+sedan',  # Days ago
            r'\d{4}-\d{2}-\d{2}',  # ISO format
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # DD/MM/YYYY
            r'(slutar|ends?)\s+(idag|today|igår|tomorrow|imorgon)',  # Ends today/yesterday
        ]
        
        listing_text = listing_element.get_text(separator=' ', strip=True)
        
        for pattern in date_patterns:
            date_match = re.search(pattern, listing_text, re.I)
            if date_match:
                posted_date = date_match.group(0).strip()
                break
        
        # Strategy 2: Look for elements with date-like classes or attributes
        if not posted_date:
            date_elem = listing_element.find(class_=re.compile(r'date|datum|time|posted|end|slutar', re.I))
            if date_elem:
                posted_date = date_elem.get_text(strip=True)
        
        # Strategy 3: Look for string nodes with date patterns
        if not posted_date:
            date_strings = listing_element.find_all(string=re.compile(r'\d{1,2}\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', re.I))
            if date_strings:
                posted_date = date_strings[0].strip()
        
        # Strategy 4: Look for "slutar" (ends) with date
        if not posted_date:
            slutar_elem = listing_element.find(string=re.compile(r'slutar', re.I))
            if slutar_elem:
                # Get parent and look for date nearby
                parent = slutar_elem.find_parent()
                if parent:
                    parent_text = parent.get_text(separator=' ', strip=True)
                    date_match = re.search(r'\d{1,2}\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)\.?', parent_text, re.I)
                    if date_match:
                        posted_date = f"Slutar {date_match.group(0)}"
        
        # Find location - Tradera often shows location
        location = None
        listing_text_for_location = listing_element.get_text(separator='\n', strip=True)
        
        # Look for Swedish cities
        swedish_cities = [
            'Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Västerås', 'Örebro',
            'Linköping', 'Helsingborg', 'Jönköping', 'Norrköping', 'Lund',
            'Umeå', 'Gävle', 'Borås', 'Eskilstuna', 'Södertälje', 'Karlstad',
            'Växjö', 'Halmstad', 'Sundsvall', 'Luleå', 'Trollhättan', 'Östersund'
        ]
        for city in swedish_cities:
            city_pattern = re.compile(rf'\b{city}\b', re.I)
            if city_pattern.search(listing_text_for_location):
                location = city
                break
        
        raw_data = {
            'html': str(listing_element)[:500]
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
    
    async def close(self):
        """Clean up browser resources and playwright"""
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
