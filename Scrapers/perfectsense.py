import asyncio
from typing import List, Optional
import re

from base import BaseScraper, ListingResult


class PerfectSenseScraper(BaseScraper):
    """Scraper for Perfect Sense demo-inbyten (trade-ins) and second-hand listings."""

    def __init__(self):
        super().__init__("https://perfect-sense.se", "Perfect Sense")
        self.category_url = f"{self.base_url}/demo-inbyten-andra-hand"

    def _parse_listing(self, node) -> Optional[ListingResult]:
        """Parse a single product from a one_third div container."""
        # Find title in h3 tag
        title_tag = node.select_one("h3")
        if not title_tag:
            return None

        title_text = title_tag.get_text(strip=True)

        # Skip sold items (marked with "Sålda")
        if "Sålda" in title_text or "sålda" in title_text.lower():
            return None

        # Extract price from "Pris: XX kr" or "Pris: XX.XXX kr" pattern
        price_value = None
        text_content = node.get_text(" ", strip=True)
        price_match = re.search(r'Pris:\s*([\d\s.,]+)\s*kr', text_content, re.IGNORECASE)
        if price_match:
            price_text = price_match.group(1)
            price_value = self._extract_price(price_text)

        # Extract image
        image_url = None
        image_tag = node.select_one("img")
        if image_tag:
            image_url = image_tag.get("src") or image_tag.get("data-src")

        # Get description text (everything before "Mer information" or "Pris:")
        description = None
        all_text = node.get_text("\n", strip=True)
        # Split by title and take text after it
        if title_text in all_text:
            text_after_title = all_text.split(title_text, 1)[1]
            # Take text before "Pris:" or "Mer information"
            desc_parts = re.split(r'(?:Pris:|Mer information)', text_after_title, maxsplit=1)
            if desc_parts:
                description = desc_parts[0].strip()
                # Limit description length
                if len(description) > 200:
                    description = description[:197] + "..."

        # No individual product URLs, use category page
        url = self.category_url

        return ListingResult(
            title=title_text,
            description=description,
            price=price_value,
            url=url,
            image_url=self._normalize_url(image_url) if image_url else None,
            posted_date=None,
            location=None,
            raw_data={"source": "perfect_sense_demo"},
        )

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        """Synchronous search - fetches single page and filters locally."""
        query_lower = (query or "").strip().lower()
        if not query_lower:
            return []

        # Fetch the single category page
        soup = self._fetch_page(self.category_url)
        if not soup:
            return []

        results: List[ListingResult] = []
        seen_titles = set()

        # Find all product containers (one_third and one_third_first divs)
        product_nodes = soup.select("div.one_third, div.one_third_first")

        for node in product_nodes:
            # Skip containers without h3 (not product items)
            if not node.select_one("h3"):
                continue

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

            # Deduplicate by title
            if listing.title in seen_titles:
                continue
            seen_titles.add(listing.title)
            results.append(listing)

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        """Async search wrapper."""
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
