from Scrapers.common import AshopCategoryScraper


class ReferenceAudioScraper(AshopCategoryScraper):
    def __init__(self):
        super().__init__(
            base_url="https://www.referenceaudio.se",
            name="Reference Audio",
            category_url="https://www.referenceaudio.se/kategori/935/begagnat",
        )
