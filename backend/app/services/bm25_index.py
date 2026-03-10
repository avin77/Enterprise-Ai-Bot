"""
BM25 index builder and government synonym query expansion.
Library: rank_bm25 (BM25Okapi variant, k1=1.5, b=0.75)
Do NOT hand-roll BM25 -- the IDF normalization formula is non-trivial.
"""
from __future__ import annotations

from rank_bm25 import BM25Okapi

# Government synonym dictionary for BM25 query expansion.
# Applied BEFORE tokenization (pre-expand query string).
# MINIMUM 30 base term keys required per CONTEXT.md locked decision.
GOVERNMENT_SYNONYMS: dict[str, list[str]] = {
    # Waste / Trash (4 base terms)
    "trash": ["waste collection", "garbage", "refuse", "rubbish", "solid waste"],
    "garbage": ["trash", "waste collection", "refuse", "rubbish"],
    "recycling": ["recyclables", "recycle", "recycling pickup", "curbside recycling"],
    "bulk trash": ["large item pickup", "bulk pickup", "junk removal", "furniture pickup"],

    # Tax and Payments (8 base terms)
    "property tax": ["real estate tax", "tax bill", "property assessment", "tax payment"],
    "personal property tax": ["vehicle tax", "car tax", "business personal property"],
    "tax bill": ["property tax", "tax statement", "tax notice"],
    "owe": ["balance", "amount due", "outstanding", "unpaid"],
    "pay": ["payment", "pay online", "pay by mail", "payment options"],
    "delinquent": ["past due", "overdue", "late payment", "delinquency"],
    "rebate": ["credit", "reimbursement", "refund", "tax relief"],
    "exemption": ["tax exemption", "homestead exemption", "senior exemption", "disability exemption"],

    # Benefits and Assistance (4 base terms)
    "snap": ["food stamps", "food assistance", "ebt", "food benefits", "supplemental nutrition"],
    "food stamps": ["snap", "ebt", "food assistance", "food benefits"],
    "benefits": ["assistance", "programs", "services", "aid", "support"],
    "welfare": ["public assistance", "benefits", "aid", "human services"],

    # Permits and Licensing (3 base terms)
    "permit": ["building permit", "zoning permit", "construction permit", "development permit"],
    "license": ["business license", "contractor license", "professional license"],
    "zoning": ["land use", "zoning regulations", "zoning variance", "rezoning"],

    # Elections and Voting (4 base terms)
    "vote": ["voter registration", "polling place", "ballot", "election"],
    "voter registration": ["register to vote", "voting registration", "voter card"],
    "polling place": ["polling location", "where to vote", "voting location", "poll site"],
    "absentee": ["mail ballot", "vote by mail", "absentee ballot", "early voting"],

    # Courts and Legal (3 base terms)
    "court": ["courthouse", "court date", "hearing", "docket"],
    "fine": ["court fee", "traffic ticket", "penalty", "citation fee"],
    "traffic ticket": ["citation", "moving violation", "court fee", "fine payment"],

    # Emergency Services (3 base terms)
    "emergency": ["911", "emergency services", "crisis", "urgent"],
    "sheriff": ["law enforcement", "police", "deputy", "non-emergency"],
    "animal control": ["stray animal", "animal complaint", "lost pet", "dog bite"],

    # Utilities (3 base terms)
    "utility": ["water bill", "electric bill", "sewer", "utility payment"],
    "water bill": ["utility payment", "water service", "water department"],
    "sewer": ["wastewater", "sewer line", "drainage", "sewage"],
}


def expand_government_query(query: str) -> str:
    """
    Pre-expand query with government synonyms before BM25 tokenization.
    Appends synonym terms to the query string (not replacing -- BM25 scores on all terms).

    Example: "trash pickup" -> "trash pickup waste collection garbage refuse rubbish solid waste"
    """
    lower = query.lower()
    extra_terms: list[str] = []

    # Check each synonym key -- longest match first to avoid partial overlaps
    for term in sorted(GOVERNMENT_SYNONYMS.keys(), key=len, reverse=True):
        if term in lower:
            extra_terms.extend(GOVERNMENT_SYNONYMS[term])

    if extra_terms:
        return query + " " + " ".join(extra_terms)
    return query


def build_bm25_index(corpus: list[dict]) -> tuple[BM25Okapi, list[dict]]:
    """
    Build BM25Okapi index from FAQ corpus.

    Args:
        corpus: list of dicts with at least {"text": str, "source_doc": str, "chunk_id": str}

    Returns:
        (bm25_index, corpus) -- corpus returned unchanged for downstream use

    BM25 parameters:
        k1=1.5: term saturation -- higher weight on term frequency (good for verbose FAQ answers)
        b=0.75: length normalization -- BM25 standard default

    Do NOT re-index per request. Call once at startup in FastAPI lifespan.
    """
    if not corpus:
        raise ValueError("Cannot build BM25 index from empty corpus. Load FAQs first.")

    tokenized = [doc["text"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized, k1=1.5, b=0.75)
    return bm25, corpus


def bm25_search(
    bm25: BM25Okapi,
    corpus: list[dict],
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """
    Run BM25 search on pre-built index. Returns top_k results.

    Args:
        bm25: pre-built BM25Okapi index
        corpus: original corpus list (parallel to bm25 index)
        query: raw user query (will be expanded + tokenized internally)
        top_k: number of results to return

    Returns:
        list of {"text": str, "source_doc": str, "chunk_id": str, "score": float}
        Always returns up to top_k results. Score may be 0 for small corpora where
        BM25 IDF normalizes to zero (e.g. corpus of 2 docs where term appears once).
    """
    expanded = expand_government_query(query)
    tokenized_query = expanded.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Sort by score descending — include all top_k regardless of zero score.
    # BM25Okapi can produce zero scores for small corpora due to IDF normalization.
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    results = []
    for i in ranked_indices[:top_k]:
        results.append({
            "text": corpus[i]["text"],
            "source_doc": corpus[i]["source_doc"],
            "chunk_id": corpus[i].get("chunk_id", f"chunk:{i}"),
            "score": float(scores[i]),
        })
    return results
