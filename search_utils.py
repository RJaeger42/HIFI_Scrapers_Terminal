from typing import List, Dict

SYNONYMS: Dict[str, List[str]] = {
    "amp": ["amplifier", "förstärkare"],
    "amplifier": ["amp", "förstärkare"],
    "förstärkare": ["amp", "amplifier"],
    "turntable": ["record player", "skivspelare"],
    "record": ["record player", "vinyl"],
    "hifi": ["audio", "audio equipment"],
}


def expand_search_term(term: str) -> List[str]:
    """
    Expand a search term by adding synonyms so that engine queries multiple variants.
    """
    normalized = term.strip().lower()
    variants = [term]
    if not normalized:
        return variants

    synonyms = SYNONYMS.get(normalized, [])
    for syn in synonyms:
        if syn not in variants:
            variants.append(syn)

    return variants
