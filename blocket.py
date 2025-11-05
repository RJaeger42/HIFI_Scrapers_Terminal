from typing import List, Optional
from bs4 import BeautifulSoup
from base import BaseScraper, ListingResult
from colors import error, info, warning, success
import re
import sys
from urllib.parse import quote_plus
from playwright.async_api import async_playwright, Browser, Page


class BlocketScraper(BaseScraper):
    """Scraper for Blocket.se (Swedish marketplace)"""
    
    def __init__(self):
        super().__init__("https://www.blocket.se", "Blocket")
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
    
    async def search(self, query: str, min_price: Optional[float] = None, 
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """Search Blocket for listings"""
        results = []
        
        # Build search URL
        search_url = f"{self.base_url}/annonser/hela_sverige"
        params = {
            'q': query,
        }
        
        if min_price:
            params['price_min'] = int(min_price)
        if max_price:
            params['price_max'] = int(max_price)
        
        param_string = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
        full_url = f"{search_url}?{param_string}"
        
        # Blocket uses JavaScript to load listings, so we need Playwright
        soup = None
        
        try:
            browser = await self._get_browser()
            page = await browser.new_page()
            
            await page.goto(full_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)  # Wait for listings to load
            
            # Wait for listing elements to appear
            try:
                await page.wait_for_selector('a[href*="/annonser/hela_sverige/"]', timeout=10000)
            except Exception:
                pass
            
            # Scroll multiple times to trigger lazy loading
            for i in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
            
            # Get rendered HTML and parse with BeautifulSoup
            content = await page.content()
            await page.close()
            
            soup = BeautifulSoup(content, 'html.parser')
        except Exception:
            # Fallback to regular fetch
            soup = self._fetch_page(full_url)
            if not soup:
                return results

            # Use the specific CSS classes from the working scraper
            # Based on the working scraper: article with class "hidZFy"
            # Strategy 1: Look for article elements with class "hidZFy" (old class name)
            listings = soup.find_all('article', class_='hidZFy')

            # Strategy 2: Look for articles with new styled-components classes
            if not listings:
                listings = soup.find_all('article', class_=lambda x: x and ('styled__Article' in str(x) or 'hCtEgx' in str(x)))
        
            # Strategy 3: Look for any article that contains prices and listing links
            if not listings:
                all_articles = soup.find_all('article')
                for article in all_articles:
                    # Check if article contains a price
                    price_text = article.find(string=re.compile(r'\d+.*kr', re.I))
                    if not price_text:
                        continue

                    # Check if article contains a link (could be in various formats)
                    links = article.find_all('a', href=True)
                    has_listing_link = False
                    for link in links:
                        href = link.get('href', '')
                        # Look for links that go to actual listings (not category pages)
                        if re.search(r'/annonser/(?:hela_sverige|[\w]+)/[^/?]+/[^/?]+', href):
                            if '?' in href:
                                url_parts = [p for p in href.split('?')[0].split('/') if p]
                                if len(url_parts) > 4:
                                    has_listing_link = True
                                    break
                            else:
                                url_parts = [p for p in href.split('/') if p]
                                if len(url_parts) >= 4:
                                    has_listing_link = True
                                    break

                    if has_listing_link and article not in listings:
                        listings.append(article)

            # Strategy 4: Fallback - look for any article with listing-like classes
            if not listings:
                listings = soup.find_all('article', class_=lambda x: x and ('item' in str(x).lower() or 'ad' in str(x).lower() or 'listing' in str(x).lower()))

            for listing in listings:
                try:
                    listing_data = self._parse_listing(listing)
                    if listing_data:
                        results.append(listing_data)
                except Exception:
                    continue
        
        return results
    
    def _parse_listing(self, listing_element) -> Optional[ListingResult]:
        """Parse a single listing element using Blocket's specific CSS classes"""
        try:
            # Based on the working scraper:
            # - Link: a with class "enigRj"
            # - Title: span with class "jzzuDW"
            # - Price: div with class "jkvRCw"
            
            # Find link using the specific class
            title_link = listing_element.find('a', class_='enigRj')
            if not title_link:
                # Fallback: try any link with href, but prefer links to actual listings
                all_links = listing_element.find_all('a', href=True)
                # Prefer links that look like actual listings (not category pages)
                for link in all_links:
                    href = link.get('href', '')
                    # Skip category links with ?cg=
                    if '?' in href and ('cg=' in href or 'q=' in href):
                        # Check if it's actually a listing (has more path parts)
                        url_parts = [p for p in href.split('?')[0].split('/') if p]
                        if len(url_parts) > 4:  # Actual listing
                            title_link = link
                            break
                    else:
                        # No query params - likely a listing
                        url_parts = [p for p in href.split('/') if p]
                        if len(url_parts) >= 4:  # /annonser/location/category/item
                            title_link = link
                            break
                
                # If still no good link, use first link
                if not title_link and all_links:
                    title_link = all_links[0]
            
            if not title_link:
                return None

            url = title_link.get('href', '')
            if not url:
                return None

            # Normalize URL (make absolute if relative)
            url = self._normalize_url(url)

            # Skip navigation/category links
            skip_patterns = [
                '/mina-annonser', '/meddelanden', '/sparade', '/mitt-blocket',
                '/sok', '/logga-in', '/registrera', '/help', '/kontakt', '/om-oss'
            ]
            if any(skip in url for skip in skip_patterns):
                return None

            # Skip category links (have query params like ?cg=)
            if '?' in url and ('cg=' in url or 'q=' in url):
                if '/annonser/hela_sverige/' in url:
                    parts = [p for p in url.split('?')[0].split('/') if p]
                    if len([p for p in parts if p]) <= 4:
                        return None
            
            # Find title using the specific class
            title_elem = listing_element.find('span', class_='jzzuDW')
            if not title_elem:
                # Try to find title in multiple places - prefer actual product titles
                # Look for headings first (h2, h3)
                title_elem = listing_element.find('h2') or listing_element.find('h3')
                if not title_elem:
                    # Try to find spans that might contain the title
                    all_spans = listing_element.find_all('span')
                    for span in all_spans:
                        text = span.get_text(strip=True)
                        # Skip category names and navigation
                        if text and len(text) > 10 and text.lower() not in [
                            'stereo & surround', 'stereo &', 'ljud & bild', 
                            'annonser', 'bevaka', 'sök', 'kategorier'
                        ]:
                            title_elem = span
                            break
                
                # Fallback: use link text
                if not title_elem:
                    title_elem = title_link
            
            title = None
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title = title_link.get_text(strip=True)
            
            # If title looks like a category name, try to get description or other text
            category_names = ['stereo & surround', 'stereo &', 'ljud & bild', 'elektronik']
            if title and any(cat in title.lower() for cat in category_names):
                # Try to find description or other text that might be the actual title
                desc_elem = listing_element.find(class_=re.compile(r'description|text|desc', re.I))
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if desc_text and len(desc_text) > 10:
                        title = desc_text.split('\n')[0].strip()  # Take first line
                else:
                    # Try to find any text that contains the search term or looks like a product name
                    all_text = listing_element.get_text(separator='\n', strip=True)
                    for line in all_text.split('\n'):
                        line = line.strip()
                        if line and len(line) > 10 and line.lower() != title.lower():
                            # Check if it doesn't look like a category or navigation
                            if not any(cat in line.lower() for cat in category_names + ['bevaka', 'sök', 'kategorier']):
                                title = line
                                break
            
            if not title or len(title) < 5:
                return None

            # Skip navigation text
            nav_text = ['annonser', 'logga in', 'lägg in', 'ny annons', 'ljud & bild', 'bevaka', 'sök', 'kategorier']
            if any(nav in title.lower() for nav in nav_text):
                return None
            
            # Find price using the specific class
            price_elem = listing_element.find('div', class_='jkvRCw')
            if not price_elem:
                # Fallback: look for price text anywhere in the element
                price_elem = listing_element.find(string=re.compile(r'\d+.*kr', re.I))
                if not price_elem:
                    price_elem = listing_element.find(class_=re.compile(r'price|pris', re.I))

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
            
            # Find description (if available)
            desc_elem = listing_element.find(class_=re.compile(r'description|text|desc', re.I))
            description = desc_elem.get_text(strip=True) if desc_elem else None
            
            # Find date (if available) - Blocket uses patterns like "Idag", "Igår", "22 sep."
            posted_date = None
            all_text = listing_element.get_text(separator=' ', strip=True)
            
            # Try Swedish date patterns
            date_patterns = [
                r'(idag|today)',  # Today
                r'(igår|yesterday)',  # Yesterday
                r'\d{1,2}\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)\.?',  # "22 sep."
                r'\d{4}-\d{2}-\d{2}',  # ISO format
            ]
            
            for pattern in date_patterns:
                date_match = re.search(pattern, all_text, re.I)
                if date_match:
                    posted_date = date_match.group(0).strip()
                    break
            
            # Try to find date in specific elements
            if not posted_date:
                date_elem = listing_element.find(string=re.compile(r'(idag|igår|\d{1,2}\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec))', re.I))
                if date_elem:
                    posted_date = date_elem.strip() if isinstance(date_elem, str) else None
            
            # Try date-like classes
            if not posted_date:
                date_elem = listing_element.find(class_=re.compile(r'date|datum|time|posted', re.I))
                if date_elem:
                    posted_date = date_elem.get_text(strip=True)
            
            # Find location (Plats)
            location = None
            # Location often appears as "Category · Location" pattern
            # Try to find text patterns like "Stereo & surround · Uppsala"
            all_text = listing_element.get_text(separator='\n', strip=True)
            
            # Look for patterns with separator (· or |)
            location_patterns = [
                re.compile(r'[^·\n]+\s*·\s*([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*)', re.I),  # "Category · Location"
                re.compile(r'[^|\n]+\s*\|\s*([A-ZÄÖÅ][a-zäöå]+(?:\s+[A-ZÄÖÅ][a-zäöå]+)*)', re.I),  # "Category | Location"
            ]
            
            for pattern in location_patterns:
                match = pattern.search(all_text)
                if match:
                    location = match.group(1).strip()
                    # Validate it's a reasonable location (Swedish city names typically start with capital)
                    if len(location) > 2 and location[0].isupper():
                        break
            
            # Fallback: Look for common Swedish city names in the text
            if not location:
                swedish_cities = [
                    'Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Västerås', 'Örebro',
                    'Linköping', 'Helsingborg', 'Jönköping', 'Norrköping', 'Lund',
                    'Umeå', 'Gävle', 'Borås', 'Eskilstuna', 'Södertälje', 'Karlstad',
                    'Växjö', 'Halmstad', 'Sundsvall', 'Luleå', 'Trollhättan', 'Östersund'
                ]
                for city in swedish_cities:
                    if city in all_text:
                        # Make sure it's not part of another word
                        city_pattern = re.compile(rf'\b{city}\b', re.I)
                        if city_pattern.search(all_text):
                            location = city
                            break
            
            
            raw_data = {
                'source': 'blocket_css_classes',
                'classes': {
                    'article': listing_element.get('class', []),
                    'link': title_link.get('class', []) if title_link else None,
                    'title': title_elem.get('class', []) if title_elem and hasattr(title_elem, 'get') else None,
                    'price': price_elem.get('class', []) if price_elem and hasattr(price_elem, 'get') else None
                }
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
        except Exception:
            return None
    
    async def _parse_playwright_listing(self, page: Page, listing_element) -> Optional[ListingResult]:
        """Parse a listing element directly from Playwright"""
        try:
            # Get URL
            url = await listing_element.get_attribute('href')
            if not url:
                # Try to find a link inside this element
                link_elem = await listing_element.query_selector('a[href*="/annonser/"]')
                if link_elem:
                    url = await link_elem.get_attribute('href')
            
            if not url:
                return None
            
            url = self._normalize_url(url)
            
            # Get title - try multiple approaches
            title = None
            title_elem = await listing_element.query_selector('h2, h3, [class*="title"], [class*="heading"]')
            if title_elem:
                title = await title_elem.inner_text()
            else:
                title = await listing_element.inner_text()
                # Take first line or reasonable chunk
                title = title.split('\n')[0].strip()
            
            if not title or len(title) < 5:
                return None
            
            # Get price
            price = None
            price_text = await listing_element.query_selector('text=/\\d+.*kr/i')
            if not price_text:
                price_elem = await listing_element.query_selector('[class*="price"], [class*="pris"]')
                if price_elem:
                    price_text_str = await price_elem.inner_text()
                    price = self._extract_price(price_text_str)
            
            if not price:
                # Try to find price in element text
                full_text = await listing_element.inner_text()
                price_match = re.search(r'(\d+[\d\s]*)\s*kr', full_text, re.I)
                if price_match:
                    price = self._extract_price(price_match.group(1))
            
            # Get image
            image_url = None
            img = await listing_element.query_selector('img')
            if img:
                image_url = await img.get_attribute('src') or await img.get_attribute('data-src')
                if image_url:
                    image_url = self._normalize_url(image_url)
            
            return ListingResult(
                title=title.strip(),
                description=None,
                price=price,
                url=url,
                image_url=image_url,
                posted_date=None,
                raw_data={'source': 'playwright_direct'}
            )
        except Exception:
            return None

