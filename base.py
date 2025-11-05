from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
import time
import requests
from bs4 import BeautifulSoup
from colors import error
import sys


@dataclass
class ListingResult:
    """Normalized listing result from scrapers"""
    title: str
    description: Optional[str]
    price: Optional[float]
    url: str
    image_url: Optional[str]
    posted_date: Optional[str]
    location: Optional[str] = None  # Location/place (e.g., "Uppsala", "Stockholm")
    raw_data: Dict = None  # Store original scraper data
    
    def __post_init__(self):
        """Initialize raw_data to empty dict if not provided"""
        if self.raw_data is None:
            self.raw_data = {}


class BaseScraper(ABC):
    """Base class for all website scrapers"""
    
    def __init__(self, base_url: str, name: str):
        self.base_url = base_url
        self.name = name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        
    def _rate_limit(self):
        """Implement rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str, retries: int = None) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage with retry logic"""
        if retries is None:
            retries = 3  # Default max retries
        
        request_timeout = 30  # Default timeout in seconds
        retry_delay = 1  # Default delay between retries in seconds
        
        for attempt in range(retries):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=request_timeout)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            except requests.exceptions.Timeout as e:
                if attempt == retries - 1:
                    print(f"{error(f'Error fetching {url} after {retries} attempts:')} Timeout - {e}", file=sys.stderr)
                    return None
                time.sleep(retry_delay * (attempt + 1))
            except requests.exceptions.HTTPError as e:
                if attempt == retries - 1:
                    # Don't log 410 Gone as errors (site may have changed structure)
                    if e.response.status_code == 410:
                        return None
                    print(f"{error(f'Error fetching {url} after {retries} attempts:')} HTTP {e.response.status_code} - {e}", file=sys.stderr)
                    return None
                time.sleep(retry_delay * (attempt + 1))
            except requests.RequestException as e:
                if attempt == retries - 1:
                    print(f"{error(f'Error fetching {url} after {retries} attempts:')} {e}", file=sys.stderr)
                    return None
                time.sleep(retry_delay * (attempt + 1))
        
        return None
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Extract price from text string"""
        import re
        # Remove currency symbols and spaces, keep numbers and commas/dots
        cleaned = re.sub(r'[^\d,.]', '', text.replace(' ', ''))
        # Replace comma with dot if it appears to be decimal separator
        if ',' in cleaned and '.' in cleaned:
            # Determine which is decimal separator based on position
            if cleaned.rindex(',') > cleaned.rindex('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Check if comma is likely decimal separator (followed by 2 digits)
            parts = cleaned.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[ListingResult]:
        """
        Search for listings matching the query
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters (min_price, max_price, etc.)
        
        Returns:
            List of ListingResult objects
        """
        pass
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to full URL if relative"""
        if url.startswith('http'):
            return url
        elif url.startswith('/'):
            return f"{self.base_url}{url}"
        else:
            return f"{self.base_url}/{url}"

