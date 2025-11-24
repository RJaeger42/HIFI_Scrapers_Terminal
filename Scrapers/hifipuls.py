import asyncio
from typing import List, Optional

from bs4 import BeautifulSoup

from base import BaseScraper, ListingResult


class HifiPulsScraper(BaseScraper):
    """Scraper that only fetches the Demo & Begagnat category page."""

    def __init__(self):
        super().__init__("https://www.hifipuls.se", "HiFi Puls")
        self.category_url = f"{self.base_url}/114-demo-begagnat"

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.category_url
        return f"{self.category_url}?p={page}"

    def _fetch_category_page(self, page: int) -> Optional[BeautifulSoup]:
        response = self.session.get(self._page_url(page), timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _parse_listing(self, node) -> Optional[ListingResult]:
        title_link = node.select_one(".product-name")
        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        url = self._normalize_url(title_link.get("href", ""))
        price_tag = node.select_one(".product-price")
        price_value = None
        if price_tag:
            price_value = self._extract_price(price_tag.get_text(" ", strip=True))

        desc = node.select_one(".product-desc")
        stock = node.select_one(".availability") or node.select_one(".product-reference")
        image_tag = node.select_one(".product-image-container img")

        return ListingResult(
            title=title,
            description=desc.get_text(" ", strip=True) if desc else None,
            price=price_value,
            url=url,
            image_url=image_tag.get("data-original") or image_tag.get("src") if image_tag else None,
            posted_date=None,
            location=stock.get_text(strip=True) if stock else None,
            raw_data={"source": "hifipuls"},
        )

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return []

        results: List[ListingResult] = []
        seen_urls = set()
        page = 1

        while page <= 5:
            soup = self._fetch_category_page(page)
            if not soup:
                break

            product_nodes = soup.select("ul.product_list li.ajax_block_product")
            if not product_nodes:
                break

            for node in product_nodes:
                listing = self._parse_listing(node)
                if not listing:
                    continue
                haystack = f"{listing.title} {listing.description or ''}"
                if not self._matches_word_boundary(haystack, query):
                    continue
                if min_price and listing.price and listing.price < min_price:
                    continue
                if max_price and listing.price and listing.price > max_price:
                    continue
                if listing.url in seen_urls:
                    continue
                seen_urls.add(listing.url)
                results.append(listing)

            # Break after first page unless pagination indicates more pages
            pagination = soup.select_one(".pagination_next a, .pagination .next a")
            if not pagination:
                break
            page += 1

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
