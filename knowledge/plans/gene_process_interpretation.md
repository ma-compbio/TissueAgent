---
name: gene_process_interpretation
status: enabled
description: >
  Identify the most likely biological process from a gene list using the
  GeneAgent cascade with MsigDB, including self-verification of claims.
  Returns a concise process interpretation with supporting evidence.
---

## Inputs
- gene_list (canonical gene symbols; non-empty)
- Optional context (organism, tissue, condition)

## Outputs
- workspace/gene_agent/<request_id>/Outputs/GeneAgent/Cascade/MsigDB_Final_Response_GeneAgent.txt
- workspace/gene_agent/<request_id>/Verification Reports/Cascade/Claims_and_Verification_for_MsigDB.txt
- workspace/gene_agent/<request_id>/Outputs/GPT-4/MsigDB_Response_GPT4.txt

## Step Sketch
Normalize gene list input → run GeneAgent process interpretation + self-verification → summarize top process call with evidence and artifact links

## Evaluation Criteria
- file_exists(workspace/gene_agent/<request_id>/Outputs/GeneAgent/Cascade/MsigDB_Final_Response_GeneAgent.txt)
- file_exists(workspace/gene_agent/<request_id>/Verification Reports/Cascade/Claims_and_Verification_for_MsigDB.txt)
- GeneAgent run artifacts saved under workspace/gene_agent/<request_id>/

## Defaults
- require_evidence_bullets: true
- include_limitations: true

## Checklist
- Prepare gene list (trim, deduplicate, preserve canonical symbols where possible)
- Run GeneAgent interpretation cascade for process naming + verification
- Write concise process summary with key evidence and limitations
- Report absolute artifact paths from workspace/gene_agent/<request_id>/
