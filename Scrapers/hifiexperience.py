from Scrapers.common import WooCommerceStoreScraper


class HifiExperienceScraper(WooCommerceStoreScraper):
    def __init__(self):
        super().__init__("https://www.hifiexperience.se", "HiFi Experience")
