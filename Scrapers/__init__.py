"""Scraper package exporting marketplace scraper classes."""

from .blocket import BlocketScraper
from .tradera import TraderaScraper
from .facebook import FacebookScraper
from .hifitorget import HifiTorgetScraper
from .hifishark import HiFiSharkScraper
from .referenceaudio import ReferenceAudioScraper
from .ljudmakarn import LjudmakarnScraper
from .hifipunkten import HiFiPunktenScraper
from .rehifi import RehifiScraper
from .audioperformance import AudioPerformanceScraper
from .hifiexperience import HifiExperienceScraper
from .audioconcept import AudioConceptScraper
from .lasseshifi import LassesHiFiScraper
from .akkelisaudio import AkkelisAudioScraper
from .hifipuls import HifiPulsScraper
from .taktoton import TaktotonScraper
from .perfectsense import PerfectSenseScraper

__all__ = [
    "BlocketScraper",
    "TraderaScraper",
    "FacebookScraper",
    "HifiTorgetScraper",
    "HiFiSharkScraper",
    "ReferenceAudioScraper",
    "LjudmakarnScraper",
    "HiFiPunktenScraper",
    "RehifiScraper",
    "AudioPerformanceScraper",
    "HifiExperienceScraper",
    "AudioConceptScraper",
    "LassesHiFiScraper",
    "AkkelisAudioScraper",
    "HifiPulsScraper",
    "TaktotonScraper",
    "PerfectSenseScraper",
]
