from Scrapers.common import StarwebSearchScraper


class RehifiScraper(StarwebSearchScraper):
    def __init__(self):
        super().__init__("https://www.rehifi.se", "Rehifi")
