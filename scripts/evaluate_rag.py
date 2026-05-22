from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from datasets import Dataset

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    # Allow running this file directly from scripts/ without installing the project as a package.
    sys.path.insert(0, str(PROJECT_ROOT))

from model.factory import embedding_model, smart_chat_model
from rag.rag_service import RagSummarizeService


DEFAULT_INPUT = Path("eval/rag_eval.sample.jsonl")
DEFAULT_OUTPUT_DIR = Path("eval/results")


def load_eval_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            item = json.loads(line)
            question = str(item.get("question") or item.get("user_input") or "").strip()
            reference = str(item.get("reference") or item.get("ground_truth") or "").strip()
            if not question or not reference:
                raise ValueError(f"{path}:{line_number} must include question and reference")

            cases.append({"question": question, "reference": reference})

    if not cases:
        raise ValueError(f"No evaluation cases found in {path}")
    return cases


def build_answer_prompt(question: str, contexts: list[str]) -> str:
    # Keep generation constrained so faithfulness reflects retrieval quality, not free-form guessing.
    context_text = "\n\n".join(
        f"[资料 {index}]\n{context}"
        for index, context in enumerate(contexts, 1)
    )
    return (
        "请只根据给定资料回答问题。"
        "如果资料不足以回答，请直接说“资料不足，无法回答”。\n\n"
        f"{context_text}\n\n"
        f"问题：{question}\n"
        "回答："
    )


def invoke_llm(prompt: str) -> str:
    response = smart_chat_model.invoke(prompt)
    return str(getattr(response, "content", response)).strip()


def build_ragas_rows(cases: list[dict[str, str]], sync: bool) -> list[dict[str, Any]]:
    rag = RagSummarizeService(sync_on_init=sync)
    rows: list[dict[str, Any]] = []

    for index, case in enumerate(cases, 1):
        question = case["question"]
        reference = case["reference"]
        docs = rag.retriever_docs(question)
        contexts = [doc.page_content for doc in docs]

        answer = invoke_llm(build_answer_prompt(question, contexts))
        rows.append(
            {
                "user_input": question,
                "retrieved_contexts": contexts,
                "response": answer,
                "reference": reference,
                # These aliases make the saved JSON easier to use with older Ragas versions too.
                "question": question,
                "contexts": contexts,
                "answer": answer,
                "ground_truth": reference,
            }
        )
        print(f"[{index}/{len(cases)}] contexts={len(contexts)} question={question}")

    return rows


def load_ragas_metrics():
    try:
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        return [faithfulness, answer_relevancy, context_precision, context_recall]
    except ImportError:
        # Ragas has renamed some metrics across releases. Keep a clear error so setup issues are obvious.
        raise RuntimeError(
            "Cannot import Ragas metrics. Install/upgrade with: "
            "python -m pip install -U ragas datasets"
        )


def run_ragas(rows: list[dict[str, Any]]):
    from ragas import evaluate

    dataset = Dataset.from_list(rows)
    return evaluate(
        dataset,
        metrics=load_ragas_metrics(),
        llm=smart_chat_model,
        embeddings=embedding_model,
    )


def save_outputs(rows: list[dict[str, Any]], result: Any, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = output_dir / "ragas_samples.json"
    scores_path = output_dir / "ragas_scores.json"
    scores_csv_path = output_dir / "ragas_scores.csv"

    samples_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        df = result.to_pandas()
        df.to_csv(scores_csv_path, index=False, encoding="utf-8-sig")
        scores_path.write_text(
            df.to_json(orient="records", force_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        scores_path.write_text(str(result), encoding="utf-8")

    print(f"Saved samples: {samples_path}")
    print(f"Saved scores:  {scores_path}")
    if scores_csv_path.exists():
        print(f"Saved csv:     {scores_csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate local RAG with Ragas.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="JSONL file. Each row needs question/reference.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for samples and Ragas scores.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync data/ before evaluation. Skip this for faster repeat runs.",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Only collect question/context/answer samples, do not run Ragas metrics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_eval_cases(args.input)
    rows = build_ragas_rows(cases, sync=args.sync)

    if args.collect_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        path = args.output_dir / "ragas_samples.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved samples: {path}")
        return

    result = run_ragas(rows)
    print(result)
    save_outputs(rows, result, args.output_dir)


if __name__ == "__main__":
    main()
