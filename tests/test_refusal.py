"""Тесты относительного критерия отказа (улучшение MVP).

Проверяют функцию is_relevant: ответ выдаётся, только если лучший фрагмент
набрал достаточный score И заметно выделяется на фоне среднего по top-k.
Это отсекает «шумные» вопросы, где совпадение по частым словам даёт
ненулевой, но равномерно низкий score по всем найденным чанкам.
"""

from app.generator import is_relevant
from app.prompts import MIN_GAP, MIN_SCORE


def _hits(scores: list[float]) -> list[dict]:
    """Собирает список хитов с заданными score (остальные поля не важны)."""
    return [
        {"doc_id": str(i), "name": f"chunk {i}", "text": "...", "score": s}
        for i, s in enumerate(scores)
    ]


def test_relevant_when_top_score_stands_out():
    # Один сильный фрагмент на фоне слабых — это настоящий ответ.
    assert is_relevant(_hits([0.30, 0.05, 0.04])) is True


def test_refuse_when_all_scores_low_and_flat():
    # Все три чанка с близким низким score — шум, должен быть отказ.
    assert is_relevant(_hits([0.21, 0.21, 0.20])) is False


def test_refuse_when_top_below_min_score():
    # Лучший фрагмент ниже минимального порога.
    assert is_relevant(_hits([0.10, 0.02, 0.01])) is False


def test_refuse_on_empty_hits():
    assert is_relevant([]) is False


def test_thresholds_are_sane():
    # Защита от случайной правки конфигурации до абсурдных значений.
    assert 0 < MIN_SCORE < 1
    assert 0 < MIN_GAP < MIN_SCORE
