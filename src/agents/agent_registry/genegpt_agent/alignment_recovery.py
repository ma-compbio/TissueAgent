"""Recover supported BLAST answers without references, new lookups or models.

Subject offsets on clones, transcripts and synthetic records are not human
chromosome coordinates. Tied natural-species hits must agree for species
identification. Historical 2,000-character excerpts often cannot meet these
requirements; abstention preserves the original answer during offline scoring.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

RULE_VERSION = "blast_linked_report_v1"
_SUMMARY_ROW = re.compile(
    r"^([\w.]+)\s+(.+?)\s{2,}([\d.]+)\s+(\S+)\s+(\d+)%\s*$", re.MULTILINE
)


def alignment_question(question: str) -> tuple[str, str] | None:
    """Recognize the two canonical task forms; never infer a task from gold."""
    patterns = (
        ("human", r"Align the DNA sequence to the human genome:\s*([ACGTN\s]+)"),
        ("species", r"Which organism does the DNA sequence come from:\s*([ACGTN\s]+)"),
    )
    for task, pattern in patterns:
        match = re.fullmatch(pattern, question.strip(), re.IGNORECASE)
        if match:
            return task, re.sub(r"\s", "", match.group(1)).upper()
    return None


def blast_request(url: str) -> dict | None:
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != "blast.ncbi.nlm.nih.gov"
            or parsed.path not in ("/blast/Blast.cgi", "/Blast.cgi")):
        return None
    return parse_qs(parsed.query)


def request_id(body: str) -> str | None:
    match = re.search(r"\bRID\s*[=:]\s*([A-Z0-9]+)\b", body)
    if match:
        return match.group(1)
    return body.strip() if re.fullmatch(r"[A-Z0-9]{10,16}", body.strip()) else None


def normalize_blast_url(url: str, api_trace: list[dict]) -> str:
    """Use the canonical endpoint and retrieve an actual submitted RID.

Text is an officially supported API format and is parsed below. Preserve
search parameters; change only the endpoint and result presentation.
"""
    query = blast_request(url)
    if query is None:
        return url
    if query.get("CMD") == ["Get"]:
        known = {
            request_id(t.get("response", t.get("response_excerpt", "")))
            for t in api_trace if (blast_request(t.get("url", "")) or {}).get("CMD") == ["Put"]
        } - {None}
        if len(query.get("RID", [])) != 1 or query["RID"][0] not in known:
            raise ValueError("BLAST Get must use the RID from a submitted Put request.")
        query["FORMAT_TYPE"] = ["Text"]
        query.pop("ALIGNMENT_VIEW", None)
    elif query.get("CMD") != ["Put"]:
        raise ValueError("BLAST requests require CMD=Put or CMD=Get.")
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path="/blast/Blast.cgi", query=urlencode(query, doseq=True)))


def _species(title: str) -> str | None:
    if re.search(r"\bsynthetic construct\b", title, re.IGNORECASE):
        return "synthetic construct"
    title = re.sub(r"^PREDICTED:\s*|^Genomic Sequence For\s+", "", title, flags=re.IGNORECASE)
    aliases = {"human": "Homo sapiens", "mouse": "Mus musculus", "zebrafish": "Danio rerio",
               "s.cerevisiae": "Saccharomyces cerevisiae", "s cerevisiae": "Saccharomyces cerevisiae"}
    for alias, name in aliases.items():
        if title.lower().startswith(alias + " "):
            return name
    match = re.match(r"([A-Za-z][a-z]+)\s+([a-z][a-z-]+)\b", title)
    if match:
        genus, species = match.groups()
        return genus.capitalize() + " " + species
    return None


def _chromosome(title: str) -> str | None:
    match = re.search(r"\bchromosome\s+(\d{1,2}|X|Y|MT)\b", title, re.IGNORECASE)
    if not match and re.search(r"\bclone\b", title, re.IGNORECASE):
        match = re.search(r"\bfrom\s+(\d{1,2}|X|Y)(?=[pq:,\s])", title, re.IGNORECASE)
    return "chr" + match.group(1).upper() if match else None


def _parse_report(body: str, sequence: str, task: str) -> dict:
    if "BLASTN" not in body:
        return {"answer": None, "reason": "no_completed_blast_report"}
    if "No significant similarity found" in body or "No hits found" in body:
        return {"answer": None, "reason": "no_hits"}
    length = re.search(r"Query=.*?\bLength=(\d+)", body, re.DOTALL)
    if not length or int(length.group(1)) != len(sequence):
        return {"answer": None, "reason": "query_length_mismatch"}
    marker = "Sequences producing significant alignments:"
    if marker not in body or "\nALIGNMENTS\n" not in body:
        return {"answer": None, "reason": "incomplete_hit_table"}
    summary, alignments = body.split(marker, 1)[1].split("\nALIGNMENTS\n", 1)
    summary = summary.split("\n", 1)[1] if "\n" in summary else ""
    rows = _SUMMARY_ROW.findall(summary)
    if not rows:
        return {"answer": None, "reason": "unparsed_hit_table"}
    # Do not silently ignore a hit whose row did not match the parser.
    nonempty = [line for line in summary.splitlines() if line.strip()]
    if len(nonempty) != len(rows):
        return {"answer": None, "reason": "incomplete_hit_table"}
    headers = {}
    for match in re.finditer(r"^>([^\s]+)\s+(.+?)\nLength=(\d+)", alignments, re.MULTILINE | re.DOTALL):
        headers[match.group(1)] = re.sub(r"\s+", " ", match.group(2)).strip()
    top_score = max(float(row[2]) for row in rows)
    top = [{"accession": a, "title": headers.get(a, t), "bits": float(b), "identity_percent": int(i)}
           for a, t, b, _, i in rows if float(b) == top_score]
    for hit in top:
        hit["species"] = _species(hit["title"])
    # Require at least one complete perfect full-query HSP from a co-best hit.
    supported = []
    blocks = re.split(r"\n(?=>)", alignments.lstrip())
    for block in blocks:
        accession = re.match(r">([^\s]+)", block)
        stats = re.search(r"Score\s*=\s*([\d.]+) bits.*?Identities\s*=\s*(\d+)/(\d+).*?Gaps\s*=\s*(\d+)/(\d+)", block, re.DOTALL)
        if not accession or not stats:
            continue
        bits, identical, total, gaps, _ = stats.groups()
        if (float(bits) == top_score and int(identical) == int(total) == len(sequence) and int(gaps) == 0
                and any(h["accession"] == accession.group(1) for h in top)):
            supported.append((accession.group(1), block))
    if not supported or any(hit["identity_percent"] != 100 for hit in top):
        return {"answer": None, "reason": "no_perfect_full_query_hsp", "top_hits": top}
    if task == "species":
        natural = [hit for hit in top if hit["species"] != "synthetic construct"]
        names = {hit["species"] for hit in natural}
        if not natural or None in names or len(names) != 1:
            return {"answer": None, "reason": "ambiguous_top_species", "top_hits": top}
        if not any(a in {h["accession"] for h in natural} for a, _ in supported):
            return {"answer": None, "reason": "no_natural_species_hsp", "top_hits": top}
        return {"answer": names.pop(), "reason": "concordant_top_species", "top_hits": top}

    human = [hit for hit in top if hit["species"] == "Homo sapiens"]
    chromosomes = {_chromosome(hit["title"]) for hit in human}
    if not human or None in chromosomes or len(chromosomes) != 1:
        return {"answer": None, "reason": "ambiguous_or_missing_human_chromosome", "top_hits": top}
    if not any(a in {h["accession"] for h in human} for a, _ in supported):
        return {"answer": None, "reason": "no_human_hsp", "top_hits": top}
    chromosome = chromosomes.pop()
    # Exact coordinates require a complete human RefSeq chromosome record.
    # Clones, RefSeqGene, transcripts and synthetic accessions give no such mapping.
    positions = set()
    mapped_accessions = set()
    for accession, block in supported:
        hit = next(h for h in human if h["accession"] == accession) if any(h["accession"] == accession for h in human) else None
        if not hit or not accession.startswith("NC_") or not re.search(r"Primary Assembly|complete sequence", hit["title"], re.IGNORECASE):
            continue
        qrows = re.findall(r"^Query\s+(\d+)\s+([A-Za-z-]+)\s+(\d+)\s*$", block, re.MULTILINE)
        srows = re.findall(r"^Sbjct\s+(\d+)\s+([A-Za-z-]+)\s+(\d+)\s*$", block, re.MULTILINE)
        if (qrows and len(qrows) == len(srows) and int(qrows[0][0]) == 1
                and int(qrows[-1][2]) == len(sequence) and "".join(r[1] for r in qrows).upper() == sequence):
            start, end = sorted((int(srows[0][0]), int(srows[-1][2])))
            positions.add((start, end))
            mapped_accessions.add(accession)
    if len(positions) == 1 and mapped_accessions == {hit["accession"] for hit in human}:
        start, end = positions.pop()
        return {"answer": f"{chromosome}:{start}-{end}", "reason": "reference_chromosome_coordinates", "top_hits": top}
    return {"answer": chromosome, "reason": "chromosome_only_no_reference_coordinates", "top_hits": top}


def recover_alignment(question: str, api_trace: list[dict]) -> dict:
    identified = alignment_question(question)
    result = {"rule": RULE_VERSION, "answer": None, "reason": "unsupported_question"}
    if identified is None:
        return result
    task, sequence = identified
    submitted = {}
    evidence = []
    reasons = []
    for index, trace in enumerate(api_trace):
        query = blast_request(trace.get("url", ""))
        if query is None:
            continue
        body = trace.get("response", trace.get("response_excerpt", ""))
        if query.get("CMD") == ["Put"]:
            sequences = query.get("QUERY", [])
            if len(sequences) == 1 and re.sub(r"\s", "", sequences[0]).upper() == sequence:
                rid = request_id(body)
                if rid:
                    submitted[rid] = index
        elif query.get("CMD") == ["Get"]:
            rid = query.get("RID", [None])[0]
            if rid not in submitted or request_id(body) != rid:
                reasons.append("unlinked_or_incomplete_report")
                continue
            parsed = _parse_report(body, sequence, task)
            item = {**parsed, "trace_index": index, "put_trace_index": submitted[rid], "rid": rid, "url": trace["url"]}
            evidence.append(item)
            reasons.append(parsed["reason"])
    answers = {item["answer"] for item in evidence if item["answer"] is not None}
    if len(answers) > 1:
        return {**result, "reason": "conflicting_reports", "evidence": evidence}
    if not answers:
        return {**result, "reason": reasons[-1] if reasons else "no_linked_blast_report", "evidence": evidence}
    if any(item["answer"] is None and item["reason"] not in {"no_completed_blast_report"} for item in evidence):
        return {**result, "reason": "conflicting_or_ambiguous_reports", "evidence": evidence}
    return {**result, "answer": answers.pop(), "reason": "linked_blast_evidence", "task": task, "evidence": evidence}
