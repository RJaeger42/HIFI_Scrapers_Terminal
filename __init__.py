# Scrapers module
from .base import BaseScraper, ListingResult
from .blocket import BlocketScraper
from .tradera import TraderaScraper
from .facebook import FacebookScraper
# HiFiSharkScraper removed - file deleted
from .hifitorget import HifiTorgetScraper

__all__ = [
    'BaseScraper',
    'ListingResult',
    'BlocketScraper',
    'TraderaScraper',
    'FacebookScraper',
    # 'HiFiSharkScraper',  # Removed
    'HifiTorgetScraper',
]

