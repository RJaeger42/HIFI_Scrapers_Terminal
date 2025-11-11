from Scrapers.common import AshopCategoryScraper


class HiFiPunktenScraper(AshopCategoryScraper):
    def __init__(self):
        super().__init__(
            base_url="https://www.hifi-punkten.se",
            name="HiFi-Punkten",
            category_url="https://www.hifi-punkten.se/kategori/1/produkter",
        )
