"""PDF → datasets.json.

Извлекает текст из учебников (PDF с текстовым слоем), режет на смысловые
записи по урокам/модулям, чистит артефакты извлечения и собирает
data/raw/datasets.json в формате, который ждёт scripts/ingest.py.

Поддерживает несколько PDF за один прогон (например Teacher's Book +
Work Book) — все записи складываются в общий datasets.json со сквозными id.

Запуск:
    uv run python scripts/pdf_to_datasets.py data/raw/pdf/Spotlight_2_TB.pdf
    uv run python scripts/pdf_to_datasets.py data/raw/pdf/*.pdf
"""

import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "raw" / "datasets.json"

# Сколько примерно символов копить в один абзац перед разрывом \n\n.
# chunker.py режет по \n\n, поэтому абзацы задают границы чанков.
PARAGRAPH_TARGET = 180
MIN_RECORD_LEN = 150


def extract_pages(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def clean(text: str) -> str:
    """Убираем служебный мусор PDF и нормализуем символы."""
    text = text.replace("\x1b", " ").replace("\r", "\n")

    # Склейка переносов слов на конце строки: "грам-\nматически" → "грамматически".
    # Дефис переноса при извлечении иногда превращается в Л или Ч.
    text = re.sub(r"([а-яёa-z])[-ЛЧ]\n([а-яёa-z])", r"\1\2", text, flags=re.I)
    # Редкий сбой: дефис-перенос превратился в Л/Ч уже без \n внутри слова.
    text = re.sub(r"([а-яё])[ЛЧ]([а-яё])", r"\1\2", text)
    # Перенос в словах ЗАГЛАВНЫМИ без дефиса: "УЧЕБНОЙ\nМЕТОДИЧЕСКОГО" склеилось
    # в "УЧЕБНОЙМЕТОДИЧЕСКОГО" — вставляем дефис на стыке (учебно-методического).
    text = re.sub(r"(УЧЕБН[А-ЯЁ]*)(МЕТОДИ[А-ЯЁ]*)", r"\1-\2", text)
    text = re.sub(r"(учебно)(методич)", r"\1-\2", text, flags=re.I)
    # Апостроф как мягкий перенос: "соот' ветствующие" → "соответствующие".
    # Только перед строчной русской буквой, чтобы не трогать англ. "What's".
    text = re.sub(r"([а-яё])'\s+([а-яё])", r"\1\2", text)

    junk_patterns = [
        r"©\s*Express Publishing.*",
        r"©\s*Prosveshcheniye.*",
        r"PHOTOCOPIABLE MATERIAL.*",
        r".*\.qxp\s+.*Page\s*\d+.*",
        r"(?:\.\s*){4,}\d*",  # точки-заполнители оглавления (в т.ч. через пробел) + номер стр.
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def to_paragraphs(text: str) -> str:
    """Склеиваем в поток и группируем по предложениям в абзацы через \\n\\n."""
    text = re.sub(r"\s*\n\s*", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    paragraphs, buf = [], ""
    for sentence in sentences:
        buf += sentence + " "
        if len(buf) > PARAGRAPH_TARGET:
            paragraphs.append(buf.strip())
            buf = ""
    if buf.strip():
        paragraphs.append(buf.strip())
    joined = "\n\n".join(paragraphs)
    # Принудительный разрыв перед заголовком раздела ЗАГЛАВНЫМИ (если он
    # оказался в середине абзаца), чтобы блок начинался со своего заголовка.
    joined = re.sub(r"\s+([А-ЯЁ][А-ЯЁ]{2,}[А-ЯЁ ]{6,})", r"\n\n\1", joined)
    return joined


def segment_lessons(text: str, source_name: str) -> list[dict]:
    """Режем на записи по маркеру 'Начало урока'; заголовок — из модуля."""
    records = []
    segments = re.split(r"(?=Начало урока)", text)
    lesson_no = 0
    for seg in segments:
        seg = seg.strip()
        if len(seg) < 120:
            continue
        lesson_no += 1
        mod = re.search(r"Модуль\s*(\d+)\s*[–\-:]\s*([^\n]{2,40})", seg)
        if mod:
            title = f"Модуль {mod.group(1)} — {mod.group(2).strip()} (урок {lesson_no})"
        else:
            title = f"{source_name} — фрагмент {lesson_no}"
        records.append({"name": title, "body": seg})
    return records


MAX_DOC_CHARS = 3000  # длинные сегменты дробим на под-документы этого размера

# Маркеры разделов: абзац, начинающийся с длинной фразы ЗАГЛАВНЫМИ буквами
# (напр. "КОМПОНЕНТЫ УМК...", "КРАТКАЯ ХАРАКТЕРИСТИКА..."). На них начинаем
# новый под-документ, чтобы тематический блок не «прилипал» к предыдущему.
SECTION_HEADER = re.compile(r"^[А-ЯЁ][А-ЯЁ \-]{8,}")


def split_into_subdocs(text: str, base_name: str) -> list[dict]:
    """Делит длинный текст на под-документы по разделам и размеру."""
    paragraphs = text.split("\n\n")
    docs, buf = [], ""

    def flush():
        if buf.strip():
            docs.append(buf.strip())

    for para in paragraphs:
        starts_section = bool(SECTION_HEADER.match(para.strip()))
        too_big = buf and len(buf) + len(para) > MAX_DOC_CHARS
        if buf and (starts_section or too_big):
            flush()
            buf = ""
        buf += para + "\n\n"
    flush()

    out = []
    for i, body in enumerate(docs):
        name = base_name if i == 0 else f"{base_name} · ч.{i + 1}"
        out.append({"name": name, "text": body})
    return out


def process_pdf(pdf_path: Path) -> list[dict]:
    source_name = pdf_path.stem
    raw = extract_pages(pdf_path)
    cleaned = clean(raw)
    out = []
    for rec in segment_lessons(cleaned, source_name):
        text = to_paragraphs(rec["body"])
        # убрать висячие номера страниц в начале
        text = re.sub(r"^\s*\.?\d{1,3}\s*", "", text).strip()
        if len(text) < MIN_RECORD_LEN:
            continue
        # длинные уроки/блоки дробим на под-документы для чистого поиска
        for sub in split_into_subdocs(text, rec["name"]):
            if len(sub["text"]) >= MIN_RECORD_LEN:
                out.append(sub)
    return out


def main() -> None:
    pdf_args = sys.argv[1:]
    if not pdf_args:
        print("Использование: python scripts/pdf_to_datasets.py <file1.pdf> [file2.pdf ...]")
        sys.exit(1)

    all_records = []
    for arg in pdf_args:
        pdf_path = Path(arg)
        if not pdf_path.exists():
            print(f"Пропуск (не найден): {pdf_path}")
            continue
        recs = process_pdf(pdf_path)
        print(f"{pdf_path.name}: {len(recs)} записей")
        all_records.extend(recs)

    datasets = [
        {"id": i, "name": r["name"], "text": r["text"]}
        for i, r in enumerate(all_records)
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"datasets": datasets}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    avg = sum(len(d["text"]) for d in datasets) // max(len(datasets), 1)
    print(f"\nИтого: {len(datasets)} записей -> {OUTPUT}")
    print(f"Средняя длина text: {avg} символов")


if __name__ == "__main__":
    main()
