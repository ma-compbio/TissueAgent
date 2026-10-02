"""Regression tests for the full paired GeneGPT benchmark harness."""

from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "benchmark"))

import run_genegpt_full_benchmark as full  # noqa: E402
import run_genegpt_paired_pilot as pilot  # noqa: E402


def test_full_corpus_counts() -> None:
    """The full corpus includes every GeneTuring and GeneHop question."""
    records = full._load_questions()

    assert len(records) == 600
    assert sum(record["scoreable"] for record in records) == 500
    assert Counter(record["suite"] for record in records) == {
        "GeneTuring": 450,
        "GeneHop": 150,
    }
    assert set(Counter(record["task"] for record in records).values()) == {50}


def test_geneturing_only_counts() -> None:
    """The GeneTuring-only selection contains nine fully scoreable tasks."""
    records = full._load_questions("GeneTuring")

    assert len(records) == 450
    assert all(record["scoreable"] for record in records)
    assert Counter(record["suite"] for record in records) == {"GeneTuring": 450}
    assert set(Counter(record["task"] for record in records).values()) == {50}


def test_completed_pilot_pairs_seed_full_run() -> None:
    """Matching pilot pairs are reused without changing their scored summary."""
    records = copy.deepcopy(full._load_questions())

    seeded = full._seed_pilot(records, full._PILOT_RECORDS)
    summary = full._summarize(records)

    assert seeded == 10
    assert summary["n_paired"] == 10
    assert summary["n_scoreable_paired"] == 10
    assert summary["direct_accuracy"] == 0.75
    assert summary["tissueagent_accuracy"] == 0.95
    assert summary["normalised_answer_agreement"] == 0.8


def test_protein_coding_sentences_are_normalized() -> None:
    """Protein-coding decisions accept explicit concise sentence forms."""
    task = "Protein-coding genes"

    assert pilot._score("Answer: Yes", "TRUE", task) == ("TRUE", 1.0)
    assert pilot._score(
        "Answer: Yes, NODAL is a protein-coding gene.", "TRUE", task
    ) == ("TRUE", 1.0)
    assert pilot._score(
        "Answer: No, ATP5F1EP2 is a pseudogene.", "NA", task
    ) == ("NA", 1.0)
    assert pilot._score(
        "LOC124903168 is not a protein-coding gene; it is uncharacterized.",
        "NA",
        task,
    ) == ("NA", 1.0)
    assert pilot._score("What is the chromosome location of BRCA1?", "NA", task)[1] == 0.0


def test_multi_species_variants_are_normalized() -> None:
    """Explicit unique species names are normalized without guessing from questions."""
    task = "Multi-species DNA aligment"

    assert pilot._score("Mus musculus (house mouse)", "mouse", task) == ("mouse", 1.0)
    assert pilot._score(
        "The DNA sequence comes from Saccharomyces cerevisiae (yeast).",
        "yeast",
        task,
    ) == ("yeast", 1.0)
    pred, score = pilot._score(
        "What chromosome is BRCA1 located on in the human genome?", "human", task
    )
    assert pred == "What chromosome is BRCA1 located on in the human genome?"
    assert score == 0.0


def test_human_alignment_prose_receives_chromosome_credit() -> None:
    """Explicit chromosomes in prose and cytobands receive upstream half-credit."""
    task = "Human genome DNA aligment"

    assert pilot._score(
        "The DNA sequence aligns to chromosome 19.",
        "chr19:41724898-41725009",
        task,
    ) == ("chr19", 0.5)
    assert pilot._score("chr6q21-22.31", "chr6:119363354-119363488", task) == (
        "chr6",
        0.5,
    )
    assert pilot._score("chr4:10-20", "chr20:10-20", task) == ("chr4:10-20", 0.0)


def test_tissueagent_timeout_is_retryable(tmp_path: Path, monkeypatch) -> None:
    """A timed-out child is recorded as an error instead of stopping the batch."""
    (tmp_path / "logs").mkdir()

    def raise_timeout(*args, **kwargs):
        raise pilot.subprocess.TimeoutExpired(args[0], timeout=1)

    monkeypatch.setattr(pilot, "_run_cli", raise_timeout)

    result = pilot._run_tissueagent(1, "test question", tmp_path, timeout=1)

    assert result["status"] == "error"
    assert result["error_type"] == "TimeoutExpired"
    assert (tmp_path / "logs/01_tissueagent.stdout").is_file()
    assert (tmp_path / "logs/01_tissueagent.stderr").is_file()


def test_recovered_answer_is_scored_without_overwriting_raw_completion():
    """A repaired runner's final answer can be derived from its last API call."""
    result = {"status": "ok", "answer": "SLC12A6", "answer_source": "ncbi_evidence_extraction",
              "raw_completion": "[https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=gene&id=9990]"}
    record = {"task": "Gene name conversion", "gold": "SLC12A6", "scoreable": True,
              "direct": copy.deepcopy(result), "tissueagent": copy.deepcopy(result)}
    full._score_record(record)
    for arm in ("direct", "tissueagent"):
        assert record[arm]["score"] == 1
        assert record[arm]["raw_completion"] == result["raw_completion"]
    summary = pilot._summarize([record])
    assert summary["direct_accuracy"] == summary["tissueagent_accuracy"] == 1


def test_historical_scoring_does_not_replace_raw_completion_with_answer():
    result = {"answer": "SLC12A6", "raw_completion": "What is BRCA1?"}
    assert pilot._answer_for_scoring(result) == "What is BRCA1?"


def test_invalid_completion_is_zero_even_for_location_or_negative_gold():
    result = {"answer": None, "answer_source": None, "raw_completion": "What is BRCA1?"}
    output = pilot._answer_for_scoring(result)
    for task, gold in (("Gene location", "chr1"), ("SNP location", "chr1"), ("Protein-coding genes", "NA")):
        assert pilot._score(output, gold, task) == ("", 0.0)


def test_direct_benchmark_retains_answer_provenance(tmp_path, monkeypatch):
    from agents.agent_registry.genegpt_agent import runner

    (tmp_path / "raw").mkdir()
    monkeypatch.setattr(runner, "run_genegpt_question", lambda *args, **kwargs: {
        "status": "ok", "answer": "SLC12A6", "answer_source": "ncbi_evidence_extraction",
        "raw_completion": "[https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=gene&id=9990]"})
    result = pilot._run_direct(1, "Convert ENSG00000140199 to official gene symbol.", tmp_path)
    assert pilot._answer_for_scoring(result) == "SLC12A6"
