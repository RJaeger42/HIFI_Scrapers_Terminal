import asyncio
from typing import List, Optional

from bs4 import BeautifulSoup

from base import BaseScraper, ListingResult


class AkkelisAudioScraper(BaseScraper):
    """Scrapes Akkelis Audio's Fyndhörnan listing."""

    def __init__(self):
        super().__init__("https://www.akkelisaudio.com", "Akkelis Audio")
        self.category_url = "https://www.akkelisaudio.com/fyndhornan/"

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").lower()
        if not query_lower:
            return []

        response = self.session.get(self.category_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select(".tws-list--grid-item")
        results: List[ListingResult] = []

        for item in items:
            title_tag = item.select_one(".tws-util-heading--heading a")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            if not self._matches_word_boundary(title, query):
                continue

            link = title_tag.get("href")
            price_current = item.select_one(".tws-api--price-current") or item.select_one(".tws-api--price-regular")
            price_text = price_current.get_text(strip=True) if price_current else None
            description = item.select_one(".tws-article-labels--label-text")
            image = item.select_one(".tws-img")
            image_url = image.get("source") if image else None

            listing = ListingResult(
                title=title,
                description=description.get_text(strip=True) if description else None,
                price=self._extract_price(price_text) if price_text else None,
                url=link,
                image_url=image_url,
                posted_date=None,
                location=None,
                raw_data={"source": "akkelis"},
            )

            if min_price and listing.price and listing.price < min_price:
                continue
            if max_price and listing.price and listing.price > max_price:
                continue
            results.append(listing)

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
