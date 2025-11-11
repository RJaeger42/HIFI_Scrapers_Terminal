from Scrapers.common import StarwebSearchScraper


class AudioPerformanceScraper(StarwebSearchScraper):
    def __init__(self):
        super().__init__("https://www.audioperformance.se", "AudioPerformance")
