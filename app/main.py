"""Streamlit UI: вопрос -> фрагменты -> ответ -> источники."""

import streamlit as st

from app.config import INDEX_CHUNKS_JSONL, MATRIX_NPZ, TOP_K, VECTORIZER_PKL
from app.generator import ask
from app.prompts import MIN_SCORE
from app.retriever import Retriever

DEMO_QUESTIONS = [
    "Что такое УМК Английский в фокусе?",
    "Как работать с диалогом на уроке?",
    "Как используются картинки на уроке?",
    "Столица Австралии",  # negative: в учебнике таких данных нет -> отказ
]


def index_exists() -> bool:
    return all(p.exists() for p in (VECTORIZER_PKL, MATRIX_NPZ, INDEX_CHUNKS_JSONL))


@st.cache_resource
def load_retriever() -> Retriever:
    return Retriever()


def render_chunk(i: int, src: dict, expanded: bool = True) -> None:
    label = f"[{i}] doc_id={src['doc_id']} · score={src['score']:.4f}"
    with st.expander(label, expanded=expanded):
        st.markdown(f"**{src['name']}**")
        st.text(src["text"])


def render_fragments(sources: list[dict]) -> None:
    st.subheader("Найденные фрагменты (top-k)")
    if not sources:
        st.info("Фрагменты не найдены.")
        return
    for i, src in enumerate(sources, 1):
        render_chunk(i, src, expanded=src["score"] >= MIN_SCORE)


def render_sources(sources: list[dict]) -> None:
    st.subheader("Источники")
    if not sources:
        st.info("Источники отсутствуют.")
        return
    for i, src in enumerate(sources, 1):
        render_chunk(i, src, expanded=False)


def main() -> None:
    st.set_page_config(page_title="RAG Tutorial", layout="wide")
    st.title("RAG Tutorial")
    st.caption("Учебный RAG: TF-IDF + demo-ответ с источниками")

    if not index_exists():
        st.error(
            "Индекс не собран. Сначала выполните:\n\n"
            "`uv run python scripts/build_index.py`"
        )
        st.stop()

    st.sidebar.header("Demo-вопросы")
    for q in DEMO_QUESTIONS:
        if st.sidebar.button(q, use_container_width=True):
            st.session_state["question"] = q

    question = st.text_input("Ваш вопрос", key="question")

    if st.button("Спросить", type="primary"):
        if not question.strip():
            st.warning("Введите вопрос.")
            st.stop()

        with st.spinner("Поиск..."):
            result = ask(question.strip(), k=TOP_K, retriever=load_retriever())

        render_fragments(result["sources"])

        st.subheader("Ответ")
        st.text(result["answer"])

        render_sources(result["sources"])


if __name__ == "__main__":
    main()
