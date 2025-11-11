from Scrapers.common import ShopifyCollectionScraper


class LassesHiFiScraper(ShopifyCollectionScraper):
    def __init__(self):
        super().__init__(
            base_url="https://lasseshifi.se",
            name="Lasses HiFi",
            collection_path="/collections/erbjudande",
        )
