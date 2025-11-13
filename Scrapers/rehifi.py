from typing import List, Optional

from base import ListingResult
from Scrapers.common import StarwebSearchScraper


class RehifiScraper(StarwebSearchScraper):
    def __init__(self):
        super().__init__("https://www.rehifi.se", "Rehifi")

    @staticmethod
    def _contains_slutsald(listing: ListingResult) -> bool:
        haystack = " ".join(
            filter(None, [listing.title, listing.description, listing.location])
        ).lower()
        return "slutsåld" in haystack or "slutsald" in haystack

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        results = await super().search(query, min_price=min_price, max_price=max_price, **kwargs)
        return [listing for listing in results if not self._contains_slutsald(listing)]
