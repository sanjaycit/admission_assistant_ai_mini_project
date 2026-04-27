"""
Module for extracting, normalizing, and resolving college entity names from user queries.
"""
import re

# ---------------------------------------------------------------------------
# Alias map — fused abbreviations → canonical compound entity key
# Used by extract_query_entities to normalise user shorthand BEFORE regex.
# Keys are lowercase; values are the canonical form stored in the cache.
# ---------------------------------------------------------------------------
COLLEGE_ALIASES: dict[str, str] = {
    # IIT campuses
    "iitb":    "iit bombay",
    "iitm":    "iit madras",
    "iitd":    "iit delhi",
    "iitk":    "iit kanpur",
    "iitkgp":  "iit kharagpur",
    "iitg":    "iit guwahati",
    "iitr":    "iit roorkee",
    "iith":    "iit hyderabad",
    "iiti":    "iit indore",
    "iitbbs":  "iit bhubaneswar",
    "iitbhu":  "iit bhu",
    "iitmandi":"iit mandi",
    # NIT campuses
    "nitk":    "nit karnataka",
    "nitt":    "nit trichy",
    "nitr":    "nit rourkela",
    "nitp":    "nit patna",
    "nitw":    "nit warangal",
    "nitc":    "nit calicut",
    # Other common colleges
    "vitc":    "vit chennai",
    "vitv":    "vit vellore",
    "srmktr":  "srm kattankulathur",
    "bitsphd": "bits pilani",
    "bitsh":   "bits hyderabad",
    "bitsg":   "bits goa",
}


def resolve_aliases(query_lower: str) -> tuple[list[str], set[str]]:
    """
    Scan every whitespace-separated token in the lowercased query against
    COLLEGE_ALIASES.  Returns:
      - found:    canonical entity keys resolved from aliases
      - consumed: original tokens that were matched (so regex steps skip them)
    """
    found: list[str] = []
    consumed: set[str] = set()
    for token in query_lower.split():
        canonical = COLLEGE_ALIASES.get(token)
        if canonical and canonical not in found:
            found.append(canonical)
            consumed.add(token)
            # Also consume the individual words of the canonical form so
            # they don't get re-added as separate entities later.
            consumed.update(canonical.split())
    return found, consumed


def extract_query_entities(query: str) -> list[str]:
    """
    Extract ALL college/institution names from the query as compound entities.

    Strategy (applied in order):
      0. Compound ACRONYM + qualifier  →  'IIT Bombay' → 'iit bombay',
                                          'NIT Trichy'  → 'nit trichy'
         These are detected FIRST so that standalone acronym scan doesn't
         split 'IIT Bombay' into separate 'iit' and 'bombay' entries.
      1. Remaining standalone ALL-CAPS acronyms not consumed by step 0
      2. Word(s) before University/College/Institute  → 'stanford'
      3. Remaining capitalized proper nouns not consumed by step 0
    """
    STOP_WORDS = {
        "what", "how", "much", "is", "the", "for", "of", "at", "in", "a", "an",
        "and", "or", "vs", "versus", "between", "compare", "both",
        "admission", "fee", "cost", "tuition", "ranking", "deadline",
        "university", "college", "institute", "school",
    }

    # ── Step -1: alias resolution (case-insensitive, handles 'iitb', 'IITB', etc.) ──
    found, consumed = resolve_aliases(query.lower())

    # ── Step 0: Compound ACRONYM + Title-case qualifier in ORIGINAL query ────
    #    Handles mixed-case input like 'IIT Bombay' that aliases don't cover.
    #    Matches: "IIT Bombay", "IIT Madras", "NIT Trichy", "BITS Pilani"
    #    Qualifier must NOT be a stop word (filters out "IIT College" etc.)
    for m in re.finditer(r'\b([A-Z]{2,})\s+([A-Z][a-z]{2,})\b', query):
        acronym, qualifier = m.group(1), m.group(2)
        acr_key, q_key = acronym.lower(), qualifier.lower()
        if q_key not in STOP_WORDS:
            key = f"{acr_key} {q_key}"   # e.g. 'iit bombay'
            if key not in found:
                found.append(key)
            consumed.add(acr_key)
            consumed.add(q_key)

    # ── Step 1: Standalone ALL-CAPS acronyms not already consumed ────────────
    for acr in re.findall(r'\b[A-Z]{2,}\b', query):
        key = acr.lower()
        if key not in STOP_WORDS and key not in found and key not in consumed:
            found.append(key)

    # 2. Name(s) directly before University / College / Institute / School
    for m in re.finditer(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:University|College|Institute|School)\b',
        query,
    ):
        key = m.group(1).lower()
        if key not in STOP_WORDS and key not in found:
            found.append(key)

    # 3. Remaining capitalized proper nouns not consumed by step 0
    for w in re.findall(r'\b[A-Z][a-z]{2,}\b', query):
        key = w.lower()
        if key not in STOP_WORDS and key not in found and key not in consumed:
            found.append(key)

    return found


def extract_query_entity(query: str) -> str | None:
    """Convenience wrapper — returns the first entity or None (single-entity queries)."""
    entities = extract_query_entities(query)
    return entities[0] if entities else None
