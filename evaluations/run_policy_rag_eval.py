# This project was developed with assistance from AI tools.
"""Run reproducible A/B/C policy RAG evaluation on the same 30-case dataset."""

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_API_PATH = _ROOT / "packages" / "api"
if str(_API_PATH) not in sys.path:
    sys.path.insert(0, str(_API_PATH))

from db.database import SessionLocal  # noqa: E402

from src.inference.client import get_embeddings  # noqa: E402
from src.services.compliance.knowledge_base.controlled_retrieval import (  # noqa: E402
    retrieve_policy_evidence,
)
from src.services.compliance.knowledge_base.search import (  # noqa: E402
    _vector_search,
    search_kb,
)

_DATASET = Path(__file__).parent / "datasets" / "fincredit_policy_pilot.json"


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _is_relevant(result, case: dict) -> bool:
    source_match = any(item in result.source_document for item in case["expected_sources"])
    if not source_match:
        return False
    if not case["expected_sections"]:
        return True
    return bool(result.section_ref) and any(
        section in result.section_ref or result.section_ref in section
        for section in case["expected_sections"]
    )


def _citation_valid(result) -> bool:
    provenance = bool(result.source_document and result.section_ref and result.effective_date)
    if result.source_type == "official":
        provenance = provenance and bool(result.source_url)
    return provenance


async def _run_case(group: str, session, case: dict):
    as_of = date.fromisoformat(case["as_of"])
    jurisdiction = case.get("jurisdiction")
    rounds = 1
    input_tokens = 0
    output_tokens = 0
    if group == "A":
        embedding = (await get_embeddings([case["question"]]))[0]
        results = await _vector_search(
            session,
            embedding,
            {
                "fetch_limit": 15,
                "as_of": as_of,
                "jurisdiction": jurisdiction,
                "source_type": None,
            },
        )
        results = results[:5]
        sufficient = bool(results)
    elif group == "B":
        results = await search_kb(
            session,
            case["question"],
            top_k=5,
            as_of=as_of,
            jurisdiction=jurisdiction,
        )
        sufficient = bool(results)
    else:
        outcome = await retrieve_policy_evidence(
            session,
            case["question"],
            as_of=as_of,
            jurisdiction=jurisdiction,
        )
        results = outcome.results[:5]
        sufficient = outcome.sufficient
        rounds = outcome.search_attempts
        input_tokens = outcome.rewrite_input_tokens or 0
        output_tokens = outcome.rewrite_output_tokens or 0
    return results, sufficient, rounds, input_tokens, output_tokens


async def evaluate(group: str, cases: list[dict]) -> dict:
    rows = []
    async with SessionLocal() as session:
        for case in cases:
            started = time.perf_counter()
            results, sufficient, rounds, input_tokens, output_tokens = await _run_case(
                group, session, case
            )
            latency_ms = (time.perf_counter() - started) * 1000
            relevant_ranks = [
                rank for rank, result in enumerate(results, 1) if _is_relevant(result, case)
            ]
            expected_count = len(case["expected_sources"])
            matched_sources = {
                expected
                for expected in case["expected_sources"]
                if any(expected in result.source_document for result in results)
            }
            recall = len(matched_sources) / expected_count if expected_count else 1.0
            rows.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "latency_ms": round(latency_ms, 2),
                    "recall_at_5": recall,
                    "reciprocal_rank": 1 / relevant_ranks[0] if relevant_ranks else 0.0,
                    "citation_correct": (
                        all(_citation_valid(result) for result in results if _is_relevant(result, case))
                        and (bool(relevant_ranks) or not case["should_answer"])
                    ),
                    "expected_answerable": case["should_answer"],
                    "predicted_answerable": sufficient,
                    "rounds": rounds,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "citations": [result.citation_id for result in results],
                }
            )

    expected_no = [not row["expected_answerable"] for row in rows]
    predicted_no = [not row["predicted_answerable"] for row in rows]
    tp = sum(expected and predicted for expected, predicted in zip(expected_no, predicted_no))
    fp = sum(not expected and predicted for expected, predicted in zip(expected_no, predicted_no))
    fn = sum(expected and not predicted for expected, predicted in zip(expected_no, predicted_no))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall_no = tp / (tp + fn) if tp + fn else 0.0
    no_answer_f1 = (
        2 * precision * recall_no / (precision + recall_no) if precision + recall_no else 0.0
    )
    return {
        "group": group,
        "dataset_size": len(rows),
        "metrics": {
            "recall_at_5": statistics.fmean(row["recall_at_5"] for row in rows),
            "mrr": statistics.fmean(row["reciprocal_rank"] for row in rows),
            "citation_correctness": statistics.fmean(
                float(row["citation_correct"]) for row in rows
            ),
            "no_answer_f1": no_answer_f1,
            "p95_latency_ms": _percentile([row["latency_ms"] for row in rows], 0.95),
            "avg_input_tokens": statistics.fmean(row["input_tokens"] for row in rows),
            "avg_output_tokens": statistics.fmean(row["output_tokens"] for row in rows),
            "avg_retrieval_rounds": statistics.fmean(row["rounds"] for row in rows),
        },
        "cases": rows,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--dataset", type=Path, default=_DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    groups = ["A", "B", "C"] if args.group == "all" else [args.group]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "definitions": {
            "A": "纯向量检索",
            "B": "向量 + PostgreSQL FTS + RRF",
            "C": "B + 最多一次查询改写与一次重试 + 证据不足拒答",
        },
        "groups": [await evaluate(group, cases) for group in groups],
    }
    output = args.output or (
        Path(__file__).parent
        / "results"
        / f"policy-rag-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    asyncio.run(main())
