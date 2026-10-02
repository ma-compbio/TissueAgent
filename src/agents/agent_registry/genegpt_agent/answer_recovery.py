"""Conservative, offline answer recovery from GeneGPT's own NCBI evidence.

The rule is intentionally limited to single Ensembl-ID-to-symbol questions.
It never accepts a reference answer, consults a database, or chooses among
multiple search hits. Historical use is post-hoc output processing, not a
reconstruction of what the model originally answered.
"""

from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlparse

RULE_VERSION = "ensembl_unique_ncbi_symbol_v1"
_QUESTION = re.compile(
    r"Convert\s+(ENSG\d{11}(?:\.\d+)?)\s+to\s+(?:the\s+)?official gene symbol\.?",
    re.IGNORECASE,
)


def _gene_request(url: str) -> tuple[str, dict]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if (parsed.scheme != "https" or parsed.hostname != "eutils.ncbi.nlm.nih.gov"
            or query.get("db") != ["gene"]):
        return "", {}
    return parsed.path, query


def recover_gene_symbol(question: str, api_trace: list[dict]) -> dict:
    """Return an answer with provenance, or a reason for abstention.

Require a complete single-hit search for the exact requested Ensembl ID,
followed by a single-ID fetch/summary of that hit with one official symbol.
Conflicting or ambiguous searches/records cause abstention. Only complete
JSON is parsed; truncated JSON excerpts are never repaired or guessed.
"""
    result = {"rule": RULE_VERSION, "answer": None, "reason": "unsupported_question"}
    match = _QUESTION.fullmatch(question.strip())
    if not match:
        return result
    ensembl = match.group(1).upper()
    result["ensembl_id"] = ensembl
    searches = []
    for index, trace in enumerate(api_trace):
        path, query = _gene_request(trace.get("url", ""))
        if (path != "/entrez/eutils/esearch.fcgi"
                or query.get("term") != [ensembl]):
            continue
        try:
            data = json.loads(trace.get("response", trace.get("response_excerpt", "")))
            search = data["esearchresult"]
            ids = search["idlist"]
            complete = (int(search["count"]) == 1 and isinstance(ids, list) and len(ids) == 1
                        and str(search.get("retstart", "0")) == "0"
                        and isinstance(ids[0], str) and ids[0].isdigit())
        except (ValueError, TypeError, KeyError, IndexError):
            return {**result, "reason": "malformed_search"}
        if not complete:
            return {**result, "reason": "ambiguous_or_empty_search"}
        searches.append((index, ids[0]))
    if not searches:
        return {**result, "reason": "no_matching_search"}
    if len({uid for _, uid in searches}) != 1:
        return {**result, "reason": "conflicting_search_hits"}

    search_index, uid = searches[0]
    evidence = []
    for index, trace in enumerate(api_trace):
        if index <= search_index:
            continue
        path, query = _gene_request(trace.get("url", ""))
        if query.get("id") != [uid]:
            continue
        body = trace.get("response", trace.get("response_excerpt", ""))
        symbols = []
        if path == "/entrez/eutils/efetch.fcgi":
            record_ids = re.findall(r"^ID:\s*(\d+)\s*$", body, re.MULTILINE)
            if record_ids and record_ids != [uid]:
                return {**result, "reason": "conflicting_record_ids"}
            symbols = re.findall(r"^Official Symbol:\s*(\S+)\s+and Name:", body, re.MULTILINE)
        elif path == "/entrez/eutils/esummary.fcgi":
            try:
                data = json.loads(body)["result"]
                record = data[uid]
                if (data["uids"] == [uid] and str(record["uid"]) == uid
                        and record.get("nomenclaturestatus", "").lower() == "official"):
                    symbols = [record["nomenclaturesymbol"]]
            except (ValueError, TypeError, KeyError):
                continue
        if len(symbols) > 1:
            return {**result, "reason": "multiple_official_symbols"}
        if (len(symbols) == 1 and isinstance(symbols[0], str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", symbols[0])):
            evidence.append({"trace_index": index, "url": trace["url"], "symbol": symbols[0]})
    if not evidence:
        return {**result, "reason": "no_complete_official_symbol"}
    if len({item["symbol"] for item in evidence}) != 1:
        return {**result, "reason": "conflicting_official_symbols"}
    return {**result, "answer": evidence[0]["symbol"], "reason": "unique_linked_official_symbol",
            "ncbi_gene_id": uid, "search_trace_index": search_index, "evidence": evidence}


def extract_terminal_answer(text: str) -> str | None:
    """Accept an explicit final answer, never a new question or tool request."""
    match = re.fullmatch(r"\s*Answer:\s*(.+?)\s*", text, re.DOTALL)
    if not match:
        return None
    answer = match.group(1).strip()
    if not answer or "?" in answer or re.search(r"https?://|\bQuestion:", answer):
        return None
    return answer
