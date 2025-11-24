import asyncio
from typing import List, Optional

from base import BaseScraper, ListingResult


class HifiExperienceScraper(BaseScraper):
    """Scraper that only looks at the Begagnad HiFi category page."""

    def __init__(self):
        super().__init__("https://www.hifiexperience.se", "HiFi Experience")
        self.category_url = f"{self.base_url}/produktkategori/begagnad-hifi/"

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.category_url
        return f"{self.category_url}page/{page}/"

    def _max_pages_from_soup(self, soup) -> Optional[int]:
        max_page = None
        for element in soup.select(".page-numbers a, .page-numbers span"):
            text = element.get_text(strip=True)
            if not text.isdigit():
                continue
            value = int(text)
            if max_page is None or value > max_page:
                max_page = value
        return max_page

    def _parse_listing(self, node) -> Optional[ListingResult]:
        link = node.select_one("a.woocommerce-LoopProduct-link")
        title_tag = node.select_one(".woocommerce-loop-product__title")
        if not link or not title_tag:
            return None

        url = link.get("href")
        price_wrapper = node.select_one(".price")
        price_value = None
        if price_wrapper:
            price_text = None
            preferred = price_wrapper.select_one("ins .amount")
            if preferred:
                price_text = preferred.get_text(strip=True)
            else:
                amount = price_wrapper.select_one(".amount")
                if amount:
                    price_text = amount.get_text(strip=True)
                else:
                    price_text = price_wrapper.get_text(strip=True)
            if price_text:
                price_value = self._extract_price(price_text)

        image = node.select_one("img")

        return ListingResult(
            title=title_tag.get_text(" ", strip=True),
            description=None,
            price=price_value,
            url=url,
            image_url=image.get("src") if image else None,
            posted_date=None,
            location=None,
            raw_data={"source": "category_page"},
        )

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return []

        results: List[ListingResult] = []
        seen_urls = set()
        page = 1
        max_page = None
        while page <= 10:
            soup = self._fetch_page(self._page_url(page))
            if not soup:
                break
            if max_page is None:
                max_page = self._max_pages_from_soup(soup)

            product_nodes = soup.select("ul.products li.product")
            if not product_nodes:
                break

            for node in product_nodes:
                listing = self._parse_listing(node)
                if not listing:
                    continue
                if not self._matches_word_boundary(listing.title, query):
                    continue
                if min_price and listing.price and listing.price < min_price:
                    continue
                if max_price and listing.price and listing.price > max_price:
                    continue
                if listing.url in seen_urls:
                    continue
                seen_urls.add(listing.url)
                results.append(listing)

            page += 1
            if max_page and page > max_page:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
