from typing import List, Optional
from bs4 import BeautifulSoup
from base import BaseScraper, ListingResult
from colors import error
import re
from urllib.parse import quote_plus


class HifiTorgetScraper(BaseScraper):
    """Scraper for HifiTorget.se (Swedish hifi marketplace)"""
    
    def __init__(self):
        super().__init__("https://www.hifitorget.se", "HifiTorget")
    
    async def search(self, query: str, min_price: Optional[float] = None,
                    max_price: Optional[float] = None, **kwargs) -> List[ListingResult]:
        """Search HifiTorget for listings"""
        results = []
        
        # Build search URL
        # Try different possible endpoints - site may have changed
        search_url = f"{self.base_url}/sok"
        params = {
            'q': query,
        }
        
        if min_price:
            params['min_pris'] = int(min_price)
        if max_price:
            params['max_pris'] = int(max_price)
        
        param_string = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])
        full_url = f"{search_url}?{param_string}"
        
        # If /sok returns 410, try /annonser
        soup = self._fetch_page(full_url)
        if not soup:
            # Try alternative endpoint
            search_url_alt = f"{self.base_url}/annonser"
            full_url_alt = f"{search_url_alt}?{param_string}"
            soup = self._fetch_page(full_url_alt)
        
        if not soup:
            return results
        
        # Try multiple selector strategies for finding listings
        listings = self._find_listings(soup)
        
        for listing in listings:
            try:
                listing_data = self._parse_listing(listing)
                if listing_data:
                    results.append(listing_data)
            except Exception as e:
                print(f"{error('Error parsing HifiTorget listing:')} {e}")
                continue
        
        return results
    
    def _find_listings(self, soup: BeautifulSoup) -> List:
        """Find listing elements using multiple strategies"""
        listings = []
        
        # Strategy 1: Look for common listing containers
        selectors = [
            ('article', {'class': re.compile(r'listing|item|annons|ad', re.I)}),
            ('div', {'class': re.compile(r'listing|item|annons|ad|product', re.I)}),
            ('div', {'data-testid': re.compile(r'listing|item|annons', re.I)}),
            ('li', {'class': re.compile(r'listing|item|annons', re.I)}),
            ('a', {'href': re.compile(r'/annons|/produkt|/listing', re.I)}),
        ]
        
        for tag, attrs in selectors:
            found = soup.find_all(tag, attrs)
            if found:
                listings.extend(found)
                break
        
        # Strategy 2: Look for links that contain listing patterns in href
        if not listings:
            listing_links = soup.find_all('a', href=re.compile(r'/annons|/produkt|/item|/listing', re.I))
            for link in listing_links:
                # Find parent container
                parent = link.find_parent(['article', 'div', 'li'])
                if parent and parent not in listings:
                    listings.append(parent)
        
        # Strategy 3: Generic fallback - look for elements with price indicators
        if not listings:
            price_elements = soup.find_all(string=re.compile(r'\d+\s*kr', re.I))
            for price_elem in price_elements:
                parent = price_elem.find_parent(['article', 'div', 'li', 'a'])
                if parent and parent not in listings:
                    listings.append(parent)
        
        return listings[:50]  # Limit to first 50 to avoid duplicates
    
    def _parse_listing(self, listing_element) -> Optional[ListingResult]:
        """Parse a single listing element"""
        # Find title and link - try multiple strategies
        title = None
        url = None
        
        # Strategy 1: Look for title in link text
        title_link = listing_element.find('a', href=True)
        if title_link:
            title = title_link.get_text(strip=True)
            url = self._normalize_url(title_link['href'])
        
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
        price_text_elem = listing_element.find(string=re.compile(r'\d+[\s.,]*\d*\s*kr', re.I))
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
        date_elem = listing_element.find(string=re.compile(
            r'\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d+\s+\w+\s+\d{4}', re.I
        ))
        if date_elem:
            posted_date = date_elem.strip()
        else:
            date_elem = listing_element.find(class_=re.compile(r'date|datum|time|posted', re.I))
            if date_elem:
                posted_date = date_elem.get_text(strip=True)
        
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

