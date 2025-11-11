import asyncio
from typing import List, Optional

from bs4 import BeautifulSoup

from base import BaseScraper, ListingResult


class HifiPulsScraper(BaseScraper):
    """PrestaShop search scraper for HiFi Puls."""

    def __init__(self):
        super().__init__("https://www.hifipuls.se", "HiFi Puls")
        self.search_url = f"{self.base_url}/search"

    def _fetch_page(self, query: str, page: int) -> BeautifulSoup:
        params = {
            "controller": "search",
            "search_query": query,
            "page": page,
        }
        response = self.session.get(self.search_url, params=params, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _parse_products(self, soup: BeautifulSoup) -> List[ListingResult]:
        items = soup.select("ul.product_list li.ajax_block_product")
        listings: List[ListingResult] = []
        for item in items:
            title_link = item.select_one(".product-name")
            if not title_link:
                continue
            title = title_link.get_text(strip=True)
            url = title_link.get("href")
            price_tag = item.select_one(".product-price")
            price_text = price_tag.get_text(strip=True) if price_tag else None
            desc = item.select_one(".product-desc")
            stock = item.select_one(".availability") or item.select_one(".product-reference")
            image_tag = item.select_one(".product-image-container img")

            listings.append(
                ListingResult(
                    title=title,
                    description=desc.get_text(strip=True) if desc else None,
                    price=self._extract_price(price_text) if price_text else None,
                    url=url,
                    image_url=image_tag.get("data-original") if image_tag else None,
                    posted_date=None,
                    location=stock.get_text(strip=True) if stock else None,
                    raw_data={"source": "hifipuls"},
                )
            )
        return listings

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").lower()
        if not query_lower:
            return []

        results: List[ListingResult] = []
        page = 1
        while True:
            soup = self._fetch_page(query, page)
            listings = self._parse_products(soup)
            if not listings:
                break
            for listing in listings:
                if min_price and listing.price and listing.price < min_price:
                    continue
                if max_price and listing.price and listing.price > max_price:
                    continue
                results.append(listing)
            page += 1
            if page > 5:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
