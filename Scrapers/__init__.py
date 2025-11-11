"""Scraper package exporting marketplace scraper classes."""

from .blocket import BlocketScraper
from .tradera import TraderaScraper
from .facebook import FacebookScraper
from .hifitorget import HifiTorgetScraper
from .hifishark import HiFiSharkScraper

__all__ = [
    "BlocketScraper",
    "TraderaScraper",
    "FacebookScraper",
    "HifiTorgetScraper",
    "HiFiSharkScraper",
]
