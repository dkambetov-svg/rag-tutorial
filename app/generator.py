"""Demo-ответ: top-k чанки -> текст + источники (без внешней LLM)."""

from app.config import TOP_K
from app.prompts import (
    MIN_GAP,
    MIN_SCORE,
    REFUSAL_EMPTY_QUESTION,
    REFUSAL_NO_CONTEXT,
)
from app.retriever import Retriever


def is_relevant(hits: list[dict]) -> bool:
    """Относительный критерий релевантности.

    Отвечаем, только если лучший фрагмент: (1) набрал score >= MIN_SCORE и
    (2) заметно выделяется на фоне среднего по top-k (отрыв >= MIN_GAP).
    Второе условие отсекает «шумные» вопросы, где все найденные чанки имеют
    близкий низкий score из-за совпадения частых слов (как/урок/что).
    """
    if not hits:
        return False
    scores = [h["score"] for h in hits]
    top1 = max(scores)
    mean_k = sum(scores) / len(scores)
    gap = top1 - mean_k
    return top1 >= MIN_SCORE and gap >= MIN_GAP


def build_answer(hits: list[dict]) -> str:
    """Формирует ответ из top-k чанков, если вопрос признан релевантным."""
    if not is_relevant(hits):
        return REFUSAL_NO_CONTEXT

    parts = ["На основании найденных фрагментов:"]
    for i, hit in enumerate(hits, 1):
        parts.append(f"\n[{i}] {hit['name']}")
        parts.append(f"doc_id={hit['doc_id']}, score={hit['score']:.2f}")
        parts.append(hit["text"])
    return "\n".join(parts)


def format_sources(hits: list[dict]) -> list[dict]:
    return [
        {
            "doc_id": hit["doc_id"],
            "name": hit.get("name", ""),
            "text": hit["text"],
            "score": hit["score"],
        }
        for hit in hits
    ]


def ask(
    question: str,
    k: int = TOP_K,
    retriever: Retriever | None = None,
) -> dict:
    """Вопрос -> ответ и список источников."""
    if not question.strip():
        return {"answer": REFUSAL_EMPTY_QUESTION, "sources": []}

    r = retriever or Retriever()
    hits = r.search(question.strip(), k=k)
    return {
        "answer": build_answer(hits),
        "sources": format_sources(hits),
    }
