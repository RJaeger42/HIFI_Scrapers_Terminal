import asyncio
from typing import List, Optional

from base import BaseScraper, ListingResult


class TaktotonScraper(BaseScraper):
    """Scraper for Taktoton.com Begagnat (used HiFi) category - Magento 2 platform."""

    def __init__(self):
        super().__init__("https://taktoton.com", "Taktoton")
        self.category_url = f"{self.base_url}/begagnat"

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.category_url
        return f"{self.category_url}?p={page}"

    def _parse_listing(self, node) -> Optional[ListingResult]:
        """Parse a single product item from Magento HTML."""
        # Find product link
        link = node.select_one("a.product-item-link")
        if not link:
            return None

        title = link.get_text(strip=True)
        url = link.get("href", "")

        # Extract price
        price_value = None
        price_tag = node.select_one("span.price")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            price_value = self._extract_price(price_text)

        # Extract image
        image_url = None
        image_tag = node.select_one("img.product-image-photo")
        if image_tag:
            image_url = image_tag.get("src") or image_tag.get("data-src")

        # Extract discount if present
        discount_tag = node.select_one(".product-item-discount")
        discount = discount_tag.get_text(strip=True) if discount_tag else None

        return ListingResult(
            title=title,
            description=discount,  # Store discount info in description
            price=price_value,
            url=self._normalize_url(url),
            image_url=image_url,
            posted_date=None,
            location=None,
            raw_data={"source": "taktoton_begagnat"},
        )

    def _has_next_page(self, soup) -> bool:
        """Check if there's a next page link."""
        # Magento pagination: look for "Nästa" (Next) link
        next_link = soup.select_one(".pages a.next, .pages a[title*='Nästa']")
        return bool(next_link)

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        """Synchronous search across paginated category pages."""
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return []

        results: List[ListingResult] = []
        seen_urls = set()
        page = 1
        max_pages = 10  # Limit to 10 pages

        while page <= max_pages:
            soup = self._fetch_page(self._page_url(page))
            if not soup:
                break

            # Magento uses ul.product-items > li.product-item
            product_nodes = soup.select("li.product-item")
            if not product_nodes:
                break

            for node in product_nodes:
                listing = self._parse_listing(node)
                if not listing:
                    continue

                # Filter by query
                haystack = f"{listing.title} {listing.description or ''}"
                if not self._matches_word_boundary(haystack, query):
                    continue

                # Filter by price
                if min_price and listing.price and listing.price < min_price:
                    continue
                if max_price and listing.price and listing.price > max_price:
                    continue

                # Deduplicate
                if listing.url in seen_urls:
                    continue
                seen_urls.add(listing.url)
                results.append(listing)

            # Check for next page
            if not self._has_next_page(soup):
                break
            page += 1

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        """Async search wrapper."""
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
