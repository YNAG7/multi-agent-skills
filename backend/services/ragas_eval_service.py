from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from model.factory import embedding_model, smart_chat_model
from rag.rag_service import RagSummarizeService


MAX_EVAL_CASES = 20


def parse_eval_jsonl(jsonl_text: str) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line_number, line in enumerate(jsonl_text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Line {line_number} is not valid JSON: {e}") from e

        question = str(item.get("question") or item.get("user_input") or "").strip()
        reference = str(item.get("reference") or item.get("ground_truth") or "").strip()
        if not question or not reference:
            raise HTTPException(status_code=400, detail=f"Line {line_number} needs question and reference")

        cases.append({"question": question, "reference": reference})

    if not cases:
        raise HTTPException(status_code=400, detail="Evaluation JSONL is empty")
    if len(cases) > MAX_EVAL_CASES:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EVAL_CASES} cases are allowed per run")

    return cases


def build_answer_prompt(question: str, contexts: list[str]) -> str:
    # Ragas should judge whether the answer follows retrieved evidence, so we keep generation grounded.
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


def build_rows(cases: list[dict[str, str]], sync: bool) -> list[dict[str, Any]]:
    rag = RagSummarizeService(sync_on_init=sync)
    rows: list[dict[str, Any]] = []

    for case in cases:
        docs = rag.retriever_docs(case["question"])
        contexts = [doc.page_content for doc in docs]
        answer = invoke_llm(build_answer_prompt(case["question"], contexts))
        rows.append(
            {
                "user_input": case["question"],
                "retrieved_contexts": contexts,
                "response": answer,
                "reference": case["reference"],
                # Aliases keep the response readable and help with older Ragas examples.
                "question": case["question"],
                "contexts": contexts,
                "answer": answer,
                "ground_truth": case["reference"],
            }
        )

    return rows


def _load_metrics():
    try:
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Ragas metrics are unavailable. Install with: python -m pip install -U ragas datasets",
        ) from e

    return [faithfulness, answer_relevancy, context_precision, context_recall]


def evaluate_jsonl(jsonl_text: str, sync: bool = False) -> dict[str, Any]:
    try:
        from datasets import Dataset
        from ragas import evaluate
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="Ragas is not installed. Install with: python -m pip install -U ragas datasets",
        ) from e

    cases = parse_eval_jsonl(jsonl_text)
    rows = build_rows(cases, sync=sync)
    result = evaluate(
        Dataset.from_list(rows),
        metrics=_load_metrics(),
        llm=smart_chat_model,
        embeddings=embedding_model,
    )

    try:
        frame = result.to_pandas()
        scores = json.loads(frame.to_json(orient="records", force_ascii=False))
        averages = {
            key: float(value)
            for key, value in frame.mean(numeric_only=True).to_dict().items()
        }
    except Exception:
        scores = []
        averages = {}

    return {
        "case_count": len(rows),
        "averages": averages,
        "scores": scores,
        "samples": rows,
    }
