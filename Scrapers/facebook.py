from typing import List, Optional
from playwright.async_api import async_playwright, Browser, Page
from base import BaseScraper, ListingResult
from colors import error
import re
import sys


class FacebookScraper(BaseScraper):
    """Scraper for Facebook Marketplace using Playwright for dynamic content"""
    
    def __init__(self):
        super().__init__("https://www.facebook.com", "Facebook Marketplace")
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def _get_browser(self) -> Browser:
        """Get or create browser instance"""
        if not self.browser:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
            except Exception as e:
                print(f"{error(f'Error initializing browser for {self.name}:')} {e}")
                raise
        return self.browser
    
    async def search(self, query: str, min_price: Optional[float] = None,
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """Search Facebook Marketplace"""
        results = []
        
        browser = await self._get_browser()
        page = await browser.new_page()
        
        try:
            # Navigate to Facebook Marketplace search
            # Set location to Sweden (Stockholm) for Swedish results
            search_url = f"{self.base_url}/marketplace/stockholm/search"
            params = {
                'query': query,
            }
            
            if min_price:
                params['minPrice'] = int(min_price)
            if max_price:
                params['maxPrice'] = int(max_price)
            
            param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{search_url}?{param_string}"
            
            await page.goto(full_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)  # Wait for dynamic content and potential login redirects
            
            # Check if we're on a login page
            current_url = page.url
            if 'login' in current_url.lower() or 'facebook.com/login' in current_url.lower():
                return results
            
            # Scroll to load more results
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
            # Try multiple selectors for listings
            listings = await page.query_selector_all('div[data-testid="marketplace-search-result-item"]')
            
            # Alternative selectors
            if not listings:
                listings = await page.query_selector_all('a[href*="/marketplace/item/"]')
            
            if not listings:
                listings = await page.query_selector_all('div[role="article"]')
            
            if not listings:
                listings = await page.query_selector_all('[data-testid*="marketplace"]')
            
            for listing in listings[:20]:  # Limit to first 20 results
                try:
                    listing_data = await self._parse_listing(page, listing)
                    if listing_data:
                        results.append(listing_data)
                except Exception:
                    continue
        
        except Exception as e:
            print(f"{error('Error searching Facebook Marketplace:')} {e}")
        finally:
            await page.close()
        
        return results
    
    async def _parse_listing(self, page: Page, listing_element) -> Optional[ListingResult]:
        """Parse a single Facebook Marketplace listing"""
        try:
            # Get link - try multiple strategies
            link_elem = await listing_element.query_selector('a[href*="/marketplace/item/"]')
            
            # If listing_element itself is a link, use it
            if not link_elem:
                tag_name = await listing_element.evaluate('el => el.tagName.toLowerCase()')
                if tag_name == 'a':
                    href = await listing_element.get_attribute('href')
                    if href and '/marketplace/item/' in href:
                        link_elem = listing_element
            
            # Try to find link in parent
            if not link_elem:
                parent = await listing_element.evaluate_handle('el => el.parentElement')
                if parent:
                    link_elem = await parent.query_selector('a[href*="/marketplace/item/"]')
            
            if not link_elem:
                return None
            
            url = await link_elem.get_attribute('href')
            if url:
                url = self._normalize_url(url)
            
            # Get title - try multiple strategies, avoiding price text
            title = None
            
            # Strategy 1: Look for span[dir="auto"] - Facebook often uses this for titles
            title_elem = await listing_element.query_selector('span[dir="auto"]')
            if title_elem:
                candidate = await title_elem.inner_text()
                # Skip if it looks like a price
                if candidate and not re.match(r'^\d+[\s,.]*\d*\s*(kr|sek|€|\$|£)', candidate.strip(), re.I):
                    title = candidate
            
            # Strategy 2: Look for h2 or h3
            if not title:
                title_elem = await listing_element.query_selector('h2, h3')
                if title_elem:
                    candidate = await title_elem.inner_text()
                    if candidate and not re.match(r'^\d+[\s,.]*\d*\s*(kr|sek|€|\$|£)', candidate.strip(), re.I):
                        title = candidate
            
            # Strategy 3: Look for span with text, but skip price-like text
            if not title:
                title_spans = await listing_element.query_selector_all('span')
                for span in title_spans[:10]:  # Check more spans
                    try:
                        text = await span.inner_text()
                        text = text.strip()
                        # Skip if it's clearly a price (starts with number + currency)
                        if text and not re.match(r'^\d+[\s,.]*\d*\s*(kr|sek|€|\$|£)', text, re.I):
                            if len(text) > 10 and len(text) < 200:
                                title = text
                                break
                    except Exception:
                        continue
            
            # Strategy 4: Get all text and use first meaningful line (skip prices)
            if not title:
                all_text = await listing_element.inner_text()
                if all_text:
                    lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                    for line in lines:
                        # Skip price lines and very short lines
                        if not re.match(r'^\d+[\s,.]*\d*\s*(kr|sek|€|\$|£)', line, re.I):
                            if len(line) > 10 and len(line) < 200:
                                title = line
                                break
            
            if not title or len(title) < 5:
                return None
            
            # Get price - try multiple strategies
            price = None
            
            # Strategy 1: Look for elements containing price patterns
            # Facebook prices are often in spans with format like "2 200 kr" or "2000 kr"
            price_elements = await listing_element.query_selector_all('span, div')
            for elem in price_elements[:15]:  # Check more elements
                try:
                    text = await elem.inner_text()
                    text = text.strip()
                    # Look for price patterns: numbers followed by kr/sek
                    if text and re.search(r'\d+[\s,.]*\d*\s*(kr|sek)', text, re.I):
                        # Try to extract just the price part
                        price_match = re.search(r'(\d+[\s,.]*\d*)\s*(kr|sek)', text, re.I)
                        if price_match:
                            price_text = price_match.group(1) + ' ' + price_match.group(2)
                            price = self._extract_price(price_text)
                            if price and price > 0:
                                break
                except Exception:
                    continue
            
            # Strategy 2: Look for price patterns in all text (more careful)
            if not price:
                all_text = await listing_element.inner_text()
                # Match prices more carefully - avoid matching long numbers
                price_matches = re.findall(r'(\d{1,6}(?:\s+\d{3})*)\s*(kr|sek)', all_text, re.I)
                if price_matches:
                    # Take first match and clean it (remove spaces between digits)
                    price_part = price_matches[0][0].replace(' ', '')
                    price = self._extract_price(price_part)
            
            # Get image
            img = await listing_element.query_selector('img')
            image_url = await img.get_attribute('src') if img else None
            
            # Get location - Facebook Marketplace usually shows location
            location = None
            try:
                # Try to find location in the listing text
                listing_text = await listing_element.inner_text()
                
                # Look for Swedish cities
                swedish_cities = [
                    'Stockholm', 'Göteborg', 'Malmö', 'Uppsala', 'Västerås', 'Örebro',
                    'Linköping', 'Helsingborg', 'Jönköping', 'Norrköping', 'Lund',
                    'Umeå', 'Gävle', 'Borås', 'Eskilstuna', 'Södertälje', 'Karlstad',
                    'Växjö', 'Halmstad', 'Sundsvall', 'Luleå', 'Trollhättan', 'Östersund'
                ]
                for city in swedish_cities:
                    if city.lower() in listing_text.lower():
                        # Make sure it's not part of another word
                        city_pattern = re.compile(rf'\b{city}\b', re.I)
                        if city_pattern.search(listing_text):
                            location = city
                            break
            except Exception:
                pass
            
            # Description
            description = None
            
            # Find date - Facebook Marketplace often shows "Posted X days ago" or similar
            posted_date = None
            try:
                listing_text = await listing_element.inner_text()
                
                # Look for relative dates
                date_patterns = [
                    r'posted\s+(\d+\s+(hours?|days?|weeks?)\s+ago)',  # "Posted 2 days ago"
                    r'(\d+\s+(hours?|days?|weeks?)\s+ago)',  # "2 days ago"
                    r'(just now|nu)',  # Just now
                    r'(today|idag)',  # Today
                    r'(yesterday|igår)',  # Yesterday
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, listing_text, re.I)
                    if date_match:
                        posted_date = date_match.group(0).strip()
                        break
                
                # Try to find date in time elements
                if not posted_date:
                    time_elem = await listing_element.query_selector('time, [datetime], [class*="time"], [class*="date"]')
                    if time_elem:
                        date_attr = await time_elem.get_attribute('datetime')
                        if date_attr:
                            posted_date = date_attr
                        else:
                            posted_date = await time_elem.inner_text()
            except Exception:
                pass
            
            raw_data = {
                'source': 'facebook_marketplace'
            }
            
            return ListingResult(
                title=title.strip(),
                description=description,
                price=price,
                url=url,
                image_url=image_url,
                posted_date=posted_date,
                location=location,
                raw_data=raw_data
            )
        except Exception as e:
            print(f"{error('Error in Facebook listing parsing:')} {e}")
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
