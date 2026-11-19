"""Starting content for a module added in the editor (valid, to be edited)."""
from __future__ import annotations

from typing import Any


def _t(languages: list[str], texts: dict[str, str]) -> dict[str, str]:
    return {code: texts.get(code, texts.get("en", "")) for code in languages}


def skeleton(mtype: str, key: str, languages: list[str], answers: list[str], randomizers: list[str]) -> dict[str, Any]:
    T = lambda pl, en: _t(languages, {"pl": pl, "en": en})  # noqa: E731
    cards = [{"code": f"C{i}", "label": T(f"karta {i}", f"card {i}")} for i in range(1, 5)]
    if mtype == "consent":
        return {"key": key, "type": "consent", "text": T("Opis badania, zasady udziału i ochrony danych.", "Description of the study, terms of participation and data protection.")}
    if mtype == "info":
        return {"key": key, "type": "info", "title": T("Informacja", "Information"), "text": T("Treść ekranu.", "Text of the screen.")}
    if mtype == "form":
        return {"key": key, "type": "form", "title": T("Pytania", "Questions"), "questions": [
            {"name": f"{key}_q1", "type": "radio", "required": True, "label": T("Pytanie", "Question"),
             "options": [{"value": "a", "label": T("odpowiedź a", "answer a")}, {"value": "b", "label": T("odpowiedź b", "answer b")}]}]}
    if mtype == "board":
        return {"key": key, "type": "board", "title": T("Plansza", "Board"), "instructions": T("Instrukcja.", "Instructions."),
                "relation": T("jedno jest przed drugim", "one comes before the other"), "kind": "arrow", "rows": 3, "elements": cards,
                "confirm_critical": True, "randomize_order": True}
    if mtype == "sob_blocks":
        items = [{"code": f"I{i}", "label": T(f"element {i}", f"item {i}")} for i in range(1, 8)]
        return {"key": key, "type": "sob_blocks", "title": T("Bloki", "Blocks"), "instructions": T("Instrukcja.", "Instructions."),
                "relation": T("jedno jest podstawą drugiego", "one is a foundation for the other"), "items": items, "design": "v7_k3_lambda1"}
    if mtype == "tap_blocks":
        items = [{"code": f"I{i}", "label": T(f"element {i}", f"item {i}")} for i in range(1, 8)]
        return {"key": key, "type": "tap_blocks", "title": T("Bloki porządkowania", "Tap-order blocks"), "instructions": T("Instrukcja.", "Instructions."),
                "criterion": T("Ułóż elementy według kryterium.", "Order the items by the criterion."), "items": items, "design": "v7_k3_lambda1",
                "anchor": {"code": "ANCHOR", "label": T("nic", "nothing")}}
    if mtype == "randomizer":
        return {"key": key, "type": "randomizer", "arms": [{"code": "A", "weight": 1}, {"code": "B", "weight": 1}], "strata_by": [], "block_multiplier": 1}
    if mtype == "stimulus":
        mod = {"key": key, "type": "stimulus", "title": T("Materiał", "Material"), "contents": {"*": {"*": T("Treść materiału.", "Text of the material.")}}}
        if randomizers:
            mod["arm_of"] = randomizers[-1]
            mod["contents"] = {}
        return mod
    if mtype == "choice":
        return {"key": key, "type": "choice", "title": T("Wybór", "Choice"), "prompt": T("Co chcesz zobaczyć?", "What would you like to see?"),
                "options": [{"value": "A", "label": T("wersja A", "version A")}, {"value": "B", "label": T("wersja B", "version B")}],
                "contents": {"A": {"*": T("Treść A.", "Text A.")}, "B": {"*": T("Treść B.", "Text B.")}}}
    if mtype == "debrief":
        return {"key": key, "type": "debrief", "text": T("Wyjaśnienie celu badania.", "Explanation of the aim of the study."), "offer_withdrawal": True}
    if mtype == "thanks":
        return {"key": key, "type": "thanks", "text": T("Dziękujemy za udział.", "Thank you for taking part.")}
    raise ValueError(mtype)
