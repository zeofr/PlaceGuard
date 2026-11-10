#!/usr/bin/env python3
"""Recall@K evaluation for PlaceGuard's retrieval layer (PlaceGuard_Evaluation_Plan.md §16).

Indexes every notice/WhatsApp message/portal event referenced anywhere in
data/gold_set.json into a scratch, throwaway ChromaDB instance (never the
live data/chroma_db), then for each gold-set case queries for the drive's
eligibility criteria and checks how many of the case's known-relevant
sources (`notices_in_scope`) show up in the top-K results.

Usage (from project root):
    python eval/eval_retrieval.py
    python eval/eval_retrieval.py --k 3 10   # also report Recall@3 and Recall@10
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from database.vector_store import PlacementVectorStore
from eval.run_eval import _load_source_index, DATA_DIR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOLD_SET_FILE = DATA_DIR / "gold_set.json"


def _resolve_text(item: dict) -> str:
    """Return the item's text, running real OCR for image-backed sources (same OCR
    call run_eval.py uses, not pre-transcribed text standing in for it)."""
    if item.get("kind") == "image":
        from extraction.ocr_client import extract_text_from_image
        image_bytes = (Path(__file__).parent.parent / item["image_path"]).read_bytes()
        return extract_text_from_image(image_bytes)
    return item["text"]


def build_scratch_store(source_index: dict) -> tuple[PlacementVectorStore, str]:
    scratch_dir = tempfile.mkdtemp(prefix="placeguard_eval_chroma_")
    store = PlacementVectorStore(persist_directory=scratch_dir, collection_name="eval_notices")

    ids, texts, metadatas = [], [], []
    for source_id, item in source_index.items():
        ids.append(source_id)
        texts.append(_resolve_text(item))
        metadatas.append({
            "drive_id": item["drive_id"],
            "source_type": item["source_type"],
            "channel": item["channel"],
        })
    store.add_notices_batch(ids, texts, metadatas)
    return store, scratch_dir


def run_retrieval_eval(ks: list[int], case_ids: set[str] | None = None, limit: int | None = None) -> None:
    gold_cases = json.loads(GOLD_SET_FILE.read_text(encoding="utf-8"))
    if case_ids:
        gold_cases = [c for c in gold_cases if c["case_id"] in case_ids]
    if limit:
        gold_cases = gold_cases[:limit]
    source_index = _load_source_index()

    print(f"Indexing {len(source_index)} sources into a scratch Chroma store...")
    store, scratch_dir = build_scratch_store(source_index)

    try:
        recalls: dict[int, list[float]] = {k: [] for k in ks}

        for case in gold_cases:
            drive_id = case["drive_id"]
            relevant = set(case.get("notices_in_scope", []))
            if not relevant:
                continue

            query = f"eligibility criteria for {drive_id}"
            max_k = max(ks)
            results = store.search_similar(query=query, n_results=max_k, drive_id=drive_id)
            retrieved_ids = [r["id"] for r in results]

            for k in ks:
                top_k = set(retrieved_ids[:k])
                hit = len(top_k & relevant)
                recalls[k].append(hit / len(relevant))

        print("\nRecall@K across all gold-set cases with a non-empty notices_in_scope:\n")
        for k in ks:
            values = recalls[k]
            mean_recall = sum(values) / len(values) if values else 0.0
            print(f"  Recall@{k:<3}: {mean_recall:.1%}  (n={len(values)} cases)")

    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument("--cases", type=str, default=None, help="Comma-separated case_ids to run.")
    parser.add_argument("--limit", type=int, default=None, help="Only run the first N cases.")
    args = parser.parse_args()
    case_ids = set(args.cases.split(",")) if args.cases else None
    run_retrieval_eval(sorted(set(args.k)), case_ids=case_ids, limit=args.limit)
