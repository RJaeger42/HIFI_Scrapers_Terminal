import asyncio
import json
import math
from typing import List, Optional, Tuple, Dict, Any

from bs4 import BeautifulSoup

from base import BaseScraper, ListingResult


class AshopCategoryScraper(BaseScraper):
    """Shared scraper for storefronts powered by Ashop (Reference Audio, Ljudmakarn, HiFi-Punkten)."""

    def __init__(self, base_url: str, name: str, category_url: str):
        super().__init__(base_url, name)
        self.category_url = category_url.rstrip("/")

    def _fetch_products_page(self, page: int) -> Tuple[List[Dict[str, Any]], int, int]:
        url = self.category_url
        separator = "&" if "?" in url else "?"
        if page > 1:
            url = f"{url}{separator}page={page}"

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.find(lambda tag: tag.has_attr(":product-data"))
        if not node:
            return [], 0, 0

        raw = node[":product-data"].replace("&quot;", '"')
        data = json.loads(raw)
        products = data.get("products", [])
        total = int(data.get("total_amount_of_products") or 0)
        per_page = int(data.get("per_page") or len(products))
        return products, total, per_page

    def _product_matches(self, product: Dict[str, Any], query: str) -> bool:
        haystack = " ".join(
            filter(
                None,
                [
                    product.get("product_name"),
                    product.get("product_title"),
                    product.get("product_info_puff"),
                ],
            )
        )
        return self._matches_word_boundary(haystack, query)

    def _product_to_listing(self, product: Dict[str, Any]) -> ListingResult:
        title = product.get("product_name") or product.get("product_title") or "Okänd produkt"
        price_text = product.get("product_display_price") or product.get("product_price")
        description = product.get("product_info_puff") or product.get("product_status_name")
        image = product.get("product_puff_image")
        url = product.get("product_url") or self._normalize_url(product.get("product_link", ""))
        location_tag = None
        tags = product.get("tags") or []
        if tags:
            location_tag = ", ".join(tag.get("product_tag_name") for tag in tags if tag.get("product_tag_name"))

        return ListingResult(
            title=title,
            description=description,
            price=self._extract_price(price_text) if price_text else None,
            url=url,
            image_url=image,
            posted_date=None,
            location=location_tag,
            raw_data={"source": "ashop", "product_id": product.get("product_id")},
        )

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        query_lower = (query or "").strip().lower()
        results: List[ListingResult] = []
        if not query_lower:
            return results

        page = 1
        max_page = None
        seen_urls = set()
        while True:
            products, total, per_page = self._fetch_products_page(page)
            if not products:
                break

            if total and per_page:
                max_page = math.ceil(total / per_page)

            for product in products:
                if not self._product_matches(product, query_lower):
                    continue
                listing = self._product_to_listing(product)
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
            if page > 10:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)


class StarwebSearchScraper(BaseScraper):
    """Scraper for Starweb storefronts (Rehifi, AudioPerformance)."""

    def __init__(self, base_url: str, name: str):
        super().__init__(base_url, name)

    def _fetch_search_page(self, query: str, page: int) -> BeautifulSoup:
        params = {"q": query, "page": page}
        response = self.session.get(f"{self.base_url}/search", params=params, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _parse_listing(self, li) -> Optional[ListingResult]:
        link = li.find("a", class_="gallery-info-link")
        if not link:
            return None
        title_tag = li.select_one(".description h3")
        price_tag = li.select_one(".product-price .amount")
        sku_tag = li.select_one(".product-sku")
        status = li.select_one(".stock-status")

        url = self._normalize_url(link.get("href", ""))
        title = title_tag.get_text(strip=True) if title_tag else link.get("title") or "Okänd produkt"
        price_text = price_tag.get_text(strip=True) if price_tag else None
        description = sku_tag.get_text(strip=True) if sku_tag else None
        location = status.get_text(strip=True) if status else None
        image = li.find("img")
        image_url = image.get("data-src") or image.get("src") if image else None

        return ListingResult(
            title=title,
            description=description,
            price=self._extract_price(price_text) if price_text else None,
            url=url,
            image_url=image_url,
            posted_date=None,
            location=location,
            raw_data={"source": "starweb"},
        )

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        results: List[ListingResult] = []
        page = 1
        seen_urls = set()

        while True:
            soup = self._fetch_search_page(query, page)
            items = soup.select("ul.products li.gallery-item")
            if not items:
                break

            for li in items:
                listing = self._parse_listing(li)
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
            if page > 5:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)


class WooCommerceStoreScraper(BaseScraper):
    """Scraper using the public WooCommerce Store API (wp-json/wc/store/products)."""

    def __init__(self, base_url: str, name: str):
        super().__init__(base_url, name)
        self.api_endpoint = f"{self.base_url}/wp-json/wc/store/products"
        self.per_page = 20

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        results: List[ListingResult] = []
        page = 1
        query = query or ""

        while True:
            params = {"search": query, "page": page, "per_page": self.per_page}
            response = self.session.get(self.api_endpoint, params=params, timeout=30)
            if response.status_code == 400:
                break
            response.raise_for_status()
            data = response.json()
            if not data:
                break

            for product in data:
                prices = product.get("prices") or {}
                price_raw = prices.get("price")
                price_value = None
                if price_raw and price_raw.isdigit():
                    divisor = 10 ** int(prices.get("currency_minor_unit", 2))
                    price_value = int(price_raw) / divisor if divisor else float(price_raw)
                if min_price and price_value and price_value < min_price:
                    continue
                if max_price and price_value and price_value > max_price:
                    continue

                listing = ListingResult(
                    title=product.get("name", "Okänd produkt"),
                    description=BeautifulSoup(product.get("short_description") or "", "html.parser").get_text(
                        " ", strip=True
                    )
                    or None,
                    price=price_value,
                    url=product.get("permalink"),
                    image_url=product.get("images", [{}])[0].get("src") if product.get("images") else None,
                    posted_date=product.get("date_created"),
                    location=None,
                    raw_data={"source": "woocommerce", "product_id": product.get("id")},
                )
                results.append(listing)

            page += 1
            if page > 5:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)


class ShopifyCollectionScraper(BaseScraper):
    """Scraper for Shopify collections via /products.json endpoint."""

    def __init__(self, base_url: str, name: str, collection_path: str):
        super().__init__(base_url, name)
        self.collection_path = collection_path.rstrip("/")

    def _fetch_page(self, page: int, limit: int = 250) -> List[Dict[str, Any]]:
        url = f"{self.base_url}{self.collection_path}/products.json"
        params = {"page": page, "limit": limit}
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("products", [])

    def _search_sync(self, query: str, min_price: Optional[float], max_price: Optional[float]) -> List[ListingResult]:
        results: List[ListingResult] = []
        page = 1

        while True:
            products = self._fetch_page(page)
            if not products:
                break

            for product in products:
                title = product.get("title", "")
                if not self._matches_word_boundary(title, query):
                    continue
                variants = product.get("variants") or []
                price_value = None
                if variants:
                    try:
                        price_value = float(variants[0].get("price"))
                    except (TypeError, ValueError):
                        price_value = None
                if min_price and price_value and price_value < min_price:
                    continue
                if max_price and price_value and price_value > max_price:
                    continue

                listing = ListingResult(
                    title=title,
                    description=BeautifulSoup(product.get("body_html") or "", "html.parser").get_text(" ", strip=True)
                    or None,
                    price=price_value,
                    url=f"{self.base_url}/products/{product.get('handle')}",
                    image_url=(product.get("image") or {}).get("src"),
                    posted_date=product.get("published_at"),
                    location=None,
                    raw_data={"source": "shopify", "product_id": product.get("id")},
                )
                results.append(listing)

            page += 1
            if page > 5:
                break

        return results

    async def search(
        self, query: str, min_price: Optional[float] = None, max_price: Optional[float] = None, **kwargs
    ) -> List[ListingResult]:
        return await asyncio.to_thread(self._search_sync, query, min_price, max_price)
