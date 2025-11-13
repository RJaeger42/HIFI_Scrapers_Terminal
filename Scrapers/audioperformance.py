import asyncio
from typing import List, Optional

from base import BaseScraper, ListingResult


class AudioPerformanceScraper(BaseScraper):
    """Scraper that only fetches the Begagnad HiFi category page."""

    def __init__(self):
        super().__init__("https://www.audioperformance.se", "AudioPerformance")
        self.category_url = f"{self.base_url}/category/begagnad-hifi"

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.category_url
        return f"{self.category_url}?page={page}"

    def _parse_listing(self, node) -> Optional[ListingResult]:
        link = node.select_one("a.gallery-info-link")
        title_tag = node.select_one(".description h3")
        if not link or not title_tag:
            return None

        price_tag = node.select_one(".product-price .amount")
        price_value = None
        if price_tag:
            price_value = self._extract_price(price_tag.get_text(" ", strip=True))

        description_tag = node.select_one(".description .product-sku") or node.select_one(".description p")
        stock_tag = node.select_one(".stock-status")
        image_tag = node.select_one("img")

        return ListingResult(
            title=title_tag.get_text(" ", strip=True),
            description=description_tag.get_text(" ", strip=True) if description_tag else None,
            price=price_value,
            url=self._normalize_url(link.get("href", "")),
            image_url=image_tag.get("data-src") or image_tag.get("src") if image_tag else None,
            posted_date=None,
            location=stock_tag.get_text(strip=True) if stock_tag else None,
            raw_data={"source": "category_page"},
        )

    def _has_next_page(self, soup) -> bool:
        pagination = soup.select_one(".pagination")
        if not pagination:
            return False
        next_link = pagination.select_one("a[rel='next'], a.next:not(.disabled)")
        return bool(next_link)

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return []

        results: List[ListingResult] = []
        seen_urls = set()
        page = 1

        while page <= 10:
            soup = self._fetch_page(self._page_url(page))
            if not soup:
                break

            product_nodes = soup.select("li.gallery-item")
            if not product_nodes:
                break

            for node in product_nodes:
                listing = self._parse_listing(node)
                if not listing:
                    continue
                haystack = f"{listing.title} {listing.description or ''}".lower()
                if query_lower not in haystack:
                    continue
                if min_price and listing.price and listing.price < min_price:
                    continue
                if max_price and listing.price and listing.price > max_price:
                    continue
                if listing.url in seen_urls:
                    continue
                seen_urls.add(listing.url)
                results.append(listing)

            if not self._has_next_page(soup):
                break
            page += 1

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
