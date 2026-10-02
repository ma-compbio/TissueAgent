"""BLAST recovery must use linked evidence and respect its coordinate system."""

import copy
from urllib.parse import urlencode

import pytest

from agents.agent_registry.genegpt_agent.alignment_recovery import (
    normalize_blast_url,
    recover_alignment,
)
from test_genegpt_answer_recovery import mock_runner

SEQ = "ACGTACGTACGT"
SPECIES = "Which organism does the DNA sequence come from:" + SEQ
HUMAN = "Align the DNA sequence to the human genome:" + SEQ
BASE = "https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi?"
RID = "ABC12345678"


def make_trace(titles=None, start=101, end=112):
    titles = titles or [("AC123456.1", "Homo sapiens chromosome 7 clone TEST, complete sequence")]
    summary = "\n".join(f"{acc} {title}  24  1e-10  100%" for acc, title in titles)
    acc, title = titles[0]
    report = f"""<p><!--
QBlastInfoBegin
Status=READY
QBlastInfoEnd
--><p>
<PRE>
BLASTN 2.17.0+
RID: {RID}
Query=
Length={len(SEQ)}
Sequences producing significant alignments:  (Bits) Value Ident
{summary}

ALIGNMENTS
>{acc} {title}
Length=1000000
 Score = 24 bits (12), Expect = 1e-10
 Identities = 12/12 (100%), Gaps = 0/12 (0%)
 Strand=Plus/Plus
Query  1  {SEQ} 12
Sbjct  {start} {SEQ} {end}
"""
    return [{"url": BASE + urlencode({"CMD": "Put", "QUERY": SEQ, "PROGRAM": "blastn", "DATABASE": "nt"}),
             "response_excerpt": RID},
            {"url": BASE + urlencode({"CMD": "Get", "RID": RID, "FORMAT_TYPE": "Text"}),
             "response_excerpt": report}]


def test_species_recovers_from_linked_perfect_alignment():
    evidence = make_trace()
    before = copy.deepcopy(evidence)
    result = recover_alignment(SPECIES, evidence)
    assert result["answer"] == "Homo sapiens"
    assert result["evidence"][0]["put_trace_index"] == 0
    assert evidence == before


def test_species_does_not_select_from_tied_species():
    evidence = make_trace([("AC1.1", "Homo sapiens chromosome 7"), ("AC2.1", "Pan troglodytes chromosome 7")])
    assert recover_alignment(SPECIES, evidence)["answer"] is None


def test_species_outside_benchmark_choices_is_not_remapped():
    evidence = make_trace([("AC1.1", "Cairina moschata chromosome 27")])
    assert recover_alignment(SPECIES, evidence)["answer"] == "Cairina moschata"


def test_explicit_synthetic_hits_are_not_natural_species():
    evidence = make_trace([("AC1.1", "Homo sapiens chromosome 7"), ("CP1.1", "Eukaryotic synthetic construct chromosome 7")])
    assert recover_alignment(SPECIES, evidence)["answer"] == "Homo sapiens"
    evidence = make_trace([("CP1.1", "Eukaryotic synthetic construct chromosome 7")])
    assert recover_alignment(SPECIES, evidence)["answer"] is None
    assert recover_alignment(HUMAN, evidence)["answer"] is None


@pytest.mark.parametrize("mutation", ["sequence", "get_rid", "body_rid", "missing_put", "waiting", "no_hits", "truncated_table", "partial_hsp"])
def test_missing_or_unlinked_evidence_is_not_recovered(mutation):
    evidence = make_trace()
    if mutation == "sequence":
        evidence[0]["url"] = evidence[0]["url"].replace(SEQ, "TTTTTTTTTTTT")
    elif mutation == "get_rid":
        evidence[1]["url"] = evidence[1]["url"].replace(RID, "OTHER1234567")
    elif mutation == "body_rid":
        evidence[1]["response_excerpt"] = evidence[1]["response_excerpt"].replace(RID, "OTHER1234567")
    elif mutation == "missing_put":
        evidence = evidence[1:]
    elif mutation == "waiting":
        evidence[1]["response_excerpt"] = f"RID: {RID}\nStatus=WAITING"
    elif mutation == "no_hits":
        evidence[1]["response_excerpt"] = f"BLASTN\nRID: {RID}\nNo significant similarity found."
    elif mutation == "truncated_table":
        evidence[1]["response_excerpt"] = evidence[1]["response_excerpt"].split("ALIGNMENTS")[0]
    elif mutation == "partial_hsp":
        evidence[1]["response_excerpt"] = evidence[1]["response_excerpt"].replace("12/12", "10/10")
    assert recover_alignment(SPECIES, evidence)["answer"] is None


@pytest.mark.parametrize("accession,title", [
    ("AC123456.1", "Homo sapiens chromosome 7 clone TEST, complete sequence"),
    ("NG_123456.1", "Homo sapiens test gene RefSeqGene on chromosome 7"),
    ("NM_123456.1", "Homo sapiens transcript from chromosome 7, mRNA"),
])
def test_local_subject_offsets_are_not_genomic_coordinates(accession, title):
    evidence = make_trace([(accession, title)], start=901, end=912)
    assert recover_alignment(HUMAN, evidence)["answer"] == "chr7"


def test_human_chromosome_conflicts_abstain():
    evidence = make_trace([("AC1.1", "Homo sapiens chromosome 7"), ("AC2.1", "Homo sapiens chromosome 8")])
    assert recover_alignment(HUMAN, evidence)["answer"] is None


@pytest.mark.parametrize("start,end", [(101, 112), (112, 101)])
def test_complete_reference_chromosome_coordinates(start, end):
    evidence = make_trace([("NC_000007.14", "Homo sapiens chromosome 7, GRCh38.p14 Primary Assembly")], start, end)
    assert recover_alignment(HUMAN, evidence)["answer"] == "chr7:101-112"


def test_reference_coordinate_span_requires_complete_query_alignment():
    evidence = make_trace([("NC_000007.14", "Homo sapiens chromosome 7, GRCh38.p14 Primary Assembly")])
    evidence[1]["response_excerpt"] = evidence[1]["response_excerpt"].split("Sbjct")[0]
    assert recover_alignment(HUMAN, evidence)["answer"] == "chr7"


def test_full_response_is_used_when_display_excerpt_is_truncated():
    evidence = make_trace()
    evidence[1]["response"] = evidence[1]["response_excerpt"]
    evidence[1]["response_excerpt"] = "<html>"
    assert recover_alignment(SPECIES, evidence)["answer"] == "Homo sapiens"


def test_url_normalization_preserves_rid_and_rejects_unsubmitted_ids():
    evidence = make_trace()
    old = evidence[1]["url"].replace("/blast/Blast.cgi", "/Blast.cgi").replace("FORMAT_TYPE=Text", "FORMAT_TYPE=XML")
    normalized = normalize_blast_url(old, evidence[:1])
    assert "/blast/Blast.cgi?" in normalized and "FORMAT_TYPE=Text" in normalized and RID in normalized
    with pytest.raises(ValueError):
        normalize_blast_url(old.replace(RID, "OTHER1234567"), evidence[:1])


def test_runner_recovers_blast_answer_and_archives_full_submission(monkeypatch, tmp_path):
    evidence = make_trace()
    put_response = f"<html>\nRID = {RID}\nRTOE = 20\n</html>"
    urls = ["[" + evidence[0]["url"] + "]", "[" + evidence[1]["url"].replace("/blast/Blast.cgi", "/Blast.cgi") + "]"]
    runner, _ = mock_runner(monkeypatch, tmp_path, urls, [put_response.encode(), evidence[1]["response_excerpt"].encode()])
    monkeypatch.setattr(runner.time, "sleep", lambda delay: None)
    result = runner.run_genegpt_question(SPECIES, request_id="blast-test")
    assert result["answer"] == "Homo sapiens"
    assert result["answer_source"] == "ncbi_evidence_extraction"
    assert result["api_trace"][0]["response"] == put_response
    assert "/blast/Blast.cgi?" in result["api_trace"][1]["url"]
    assert "/Blast.cgi?" in result["api_trace"][1]["requested_url"]


def test_unsubmitted_rid_does_not_execute_and_stays_within_call_cap(monkeypatch, tmp_path):
    runner, _ = mock_runner(monkeypatch, tmp_path, [f"[{BASE}CMD=Get&RID={RID}]"] * 2)
    monkeypatch.setattr(runner, "_MAX_CALLS", 2)
    result = runner.run_genegpt_question(SPECIES, request_id="blast-test")
    assert result["status"] == "error"
    assert result["num_calls"] == 2 and result["ncbi_calls"] == 0


def test_rid_only_completion_is_not_a_final_answer(monkeypatch, tmp_path):
    evidence = make_trace()
    runner, _ = mock_runner(monkeypatch, tmp_path, ["[" + evidence[0]["url"] + "]", f"Answer: [{RID}]"], [RID.encode()])
    monkeypatch.setattr(runner, "_MAX_CALLS", 2)
    result = runner.run_genegpt_question(SPECIES, request_id="blast-test")
    assert result["status"] == "error" and result["answer"] is None
