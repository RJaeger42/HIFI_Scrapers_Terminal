from Scrapers.common import WooCommerceStoreScraper


class AudioConceptScraper(WooCommerceStoreScraper):
    def __init__(self):
        super().__init__("https://audioconcept.se", "AudioConcept")
