from Scrapers.common import AshopCategoryScraper


class LjudmakarnScraper(AshopCategoryScraper):
    def __init__(self):
        super().__init__(
            base_url="https://www.ljudmakarn.se",
            name="Ljudmakarn",
            category_url="https://www.ljudmakarn.se/kategori/107/fyndhornan",
        )
