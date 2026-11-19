"""Demonstration surveys: one per technique and one that uses every module type.

The examples concern planning a research project and the sources a student turns
to; they show the techniques and carry no study.
"""
from __future__ import annotations

import copy
from typing import Any

from ..survey.schema import BUNDLE_FORMAT, BUNDLE_VERSION


def L(pl: str, en: str) -> dict[str, str]:
    return {"pl": pl, "en": en}


PROJECT_CARDS = [
    ("RQ", L("pytanie badawcze", "research question")),
    ("LIT", L("przegląd literatury", "literature review")),
    ("METH", L("wybór metody", "choice of method")),
    ("DATA", L("zbieranie danych", "data collection")),
    ("ANAL", L("analiza", "analysis")),
]
PROJECT_RELATION = L("jedno musi być ustalone, zanim da się dobrze wykonać drugie", "one must be settled before the other can be done well")

REVIEW_STEPS = [
    ("TOPIC", L("określenie tematu", "defining the topic")),
    ("DB", L("wybór baz danych", "choosing databases")),
    ("QUERY", L("ułożenie zapytania", "building the search query")),
    ("SCREEN", L("selekcja wyników", "screening the results")),
    ("READ", L("lektura pełnych tekstów", "reading the full texts")),
    ("NOTES", L("notatki i ekstrakcja danych", "notes and data extraction")),
    ("SYNTH", L("pisanie syntezy", "writing the synthesis")),
]

SOURCES = [
    ("SUP", L("promotor lub opiekun", "supervisor")),
    ("PEER", L("koleżanki i koledzy", "fellow students")),
    ("DBS", L("bazy danych biblioteki", "library databases")),
    ("LIBN", L("bibliotekarz dziedzinowy", "subject librarian")),
    ("CHAT", L("czat z modelem językowym", "AI chatbot")),
    ("FORUM", L("fora internetowe", "online forums")),
    ("BOOK", L("podręczniki", "textbooks")),
]

FANO = [[0, 1, 2], [0, 3, 4], [0, 5, 6], [1, 3, 5], [1, 4, 6], [2, 3, 6], [2, 4, 5]]

CONSENT = L(
    "To jest **pokaz** techniki. Odpowiedzi trafiają do bazy demonstracyjnej i nie służą żadnemu badaniu.\n\nMożesz w każdej chwili zrezygnować; Twoje odpowiedzi zostaną wtedy usunięte.",
    "This is a **demonstration** of the technique. Answers go to a demonstration database and serve no study.\n\nYou can withdraw at any time; your answers are then deleted.",
)
THANKS = L("Dziękujemy. Pokaz został zakończony.", "Thank you. The demonstration is complete.")


def _cards(rows):
    return [{"code": c, "label": lab} for c, lab in rows]


def _bundle(title: dict[str, str], description: dict[str, str], modules: list[dict[str, Any]], retest: bool = False) -> dict[str, Any]:
    return copy.deepcopy({
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "survey": {"title": title, "description": description, "languages": ["pl", "en"], "default_language": "pl",
                   "detect_browser_language": True, "allow_language_switch": True, "retest": retest},
        "modules": modules,
    })


BOARD_INSTRUCTIONS = {
    "tier": L("Połóż każdą kartę w jednym z rzędów. Karta w niższym rzędzie jest przed kartą w wyższym. Karty w tym samym rzędzie nie mają między sobą kolejności.",
              "Put every card in one of the rows. A card in a lower row comes before a card in a higher row. Cards in the same row have no order between them."),
    "tier_aside": L("Połóż każdą kartę w jednym z rzędów albo odłóż ją na bok. Karta odłożona na bok nie pozostaje w relacji z żadną inną kartą.",
                    "Put every card in one of the rows or set it aside. A card set aside stands in no relation to any other card."),
    "arrow": L("Dotknij karty, a potem karty, która jest po niej, aby narysować strzałkę. Strzałki wynikające z narysowanych pojawią się same.",
               "Tap a card and then the card that comes after it to draw an arrow. Arrows implied by the drawn ones appear by themselves."),
    "pile": L("Rozłóż karty na stosy. Karty w jednym stosie należą do siebie.",
              "Sort the cards into piles. Cards in one pile belong together."),
    "plane": L("Postaw każdą kartę w punkcie planszy. Karta jest przed inną, gdy leży na lewo od niej i niżej.",
               "Place every card at a point of the board. A card comes before another when it lies to the left of it and below it."),
    "pairs": L("Odpowiedz osobno dla każdej pary kart.", "Answer for every pair of cards separately."),
}

BOARD_TITLES = {
    "tier": L("Plansza rzędów", "Tier board"),
    "tier_aside": L("Plansza rzędów z miejscem na bok", "Tier board with an aside region"),
    "arrow": L("Plansza strzałek", "Arrow board"),
    "pile": L("Plansza stosów", "Pile board"),
    "plane": L("Plansza punktów", "Plane board"),
    "pairs": L("Porównania parami", "Pairwise questions"),
}


def board_demo(kind: str) -> dict[str, Any]:
    module = {
        "key": "board", "type": "board", "title": BOARD_TITLES[kind], "instructions": BOARD_INSTRUCTIONS[kind],
        "relation": PROJECT_RELATION if kind != "pile" else L("oba należą do tej samej części pracy", "both belong to the same part of the work"),
        "kind": kind, "elements": _cards(PROJECT_CARDS), "randomize_order": True,
    }
    if kind in ("tier", "tier_aside"):
        module["rows"] = 3
    if kind == "arrow":
        module["confirm_critical"] = True
    title = L("Pokaz: " + BOARD_TITLES[kind]["pl"].lower(), "Demonstration: " + BOARD_TITLES[kind]["en"].lower())
    return _bundle(title, L("Etapy projektu badawczego na jednej planszy.", "Stages of a research project on one board."), [
        {"key": "consent", "type": "consent", "text": CONSENT},
        module,
        {"key": "thanks", "type": "thanks", "text": THANKS},
    ])


def sob_demo() -> dict[str, Any]:
    return _bundle(L("Pokaz: Subjective Order Blocks", "Demonstration: Subjective Order Blocks"),
                   L("Kroki przeglądu literatury w blokach po trzy.", "Steps of a literature review in blocks of three."), [
        {"key": "consent", "type": "consent", "text": CONSENT},
        {"key": "steps", "type": "sob_blocks", "title": L("Kroki przeglądu literatury", "Steps of a literature review"),
         "instructions": L("Ułóż elementy bloku na poziomach. Element na niższym poziomie jest podstawą dla elementu na wyższym. Elementy na tym samym poziomie albo w schowku nie mają między sobą kolejności.",
                           "Place the items of the block on levels. An item on a lower level is a foundation for an item on a higher level. Items on the same level or in the side bin have no order between them."),
         "relation": L("jedno musi być gotowe, zanim drugie ma sens", "one has to be in place before the other makes sense"),
         "items": _cards(REVIEW_STEPS),
         "blocks": [[REVIEW_STEPS[i][0] for i in b] for b in FANO]},
        {"key": "thanks", "type": "thanks", "text": THANKS},
    ])


def tap_demo() -> dict[str, Any]:
    return _bundle(L("Pokaz: bloki porządkowania z kartą odniesienia", "Demonstration: tap-order blocks with an anchor"),
                   L("Źródła pomocy w pracy nad tekstem, porządkowane względem karty „nic / nikt”.", "Sources of help with a text, ordered against the card 'nothing / no one'."), [
        {"key": "consent", "type": "consent", "text": CONSENT},
        {"key": "practice", "type": "tap_blocks", "practice": True, "title": L("Blok próbny", "Practice block"),
         "instructions": L("Dotykaj kart w kolejności: najpierw tę, która pasuje najbardziej. Pomyłkę cofniesz przyciskiem „Cofnij”.",
                           "Tap the cards in order: first the one that fits best. Undo a mistake with the 'Undo' button."),
         "criterion": L("Ułóż owoce od najsłodszego do najmniej słodkiego.", "Order the fruit from the sweetest to the least sweet."),
         "items": _cards([("BAN", L("banan", "banana")), ("LEM", L("cytryna", "lemon")), ("APL", L("jabłko", "apple"))]),
         "blocks": [["BAN", "LEM", "APL"]], "shuffle_blocks": False},
        {"key": "value", "type": "tap_blocks", "title": L("Co może dać każde źródło", "What each source could give"),
         "instructions": L("Na każdym ekranie dotknij kart w kolejności. Karta „nic / nikt” jest punktem odniesienia: źródła, które dotkniesz po niej, nie dałyby Ci teraz nic.",
                           "On every screen tap the cards in order. The card 'nothing / no one' is the reference: sources you tap after it would give you nothing right now."),
         "criterion": L("Ułóż źródła według tego, ile każde z nich mogłoby Ci teraz dać do pracy nad tekstem.", "Order the sources by how much each could give you for your text right now."),
         "items": _cards(SOURCES), "design": "v7_k3_lambda1",
         "anchor": {"code": "ANCHOR", "label": L("nic / nikt", "nothing / no one")},
         "gate": {"question": L("Czy ten blok był dla Ciebie łatwy?", "Was this block easy for you?"),
                  "options": [{"value": "yes", "label": L("tak", "yes")}, {"value": "no", "label": L("nie", "no")}]},
         "duplicates": 1, "attention": 1,
         "attention_label": L("Tej karty dotknij na końcu", "Tap this card last")},
        {"key": "thanks", "type": "thanks", "text": THANKS},
    ])


def experiment_demo() -> dict[str, Any]:
    summary_a = L(
        "**Lista źródeł (format katalogowy)**\n\n- Kowalska, A. (2021). Metody przeglądu literatury. *Studia Informacyjne*, 12(3), 45–60. https://doi.org/10.0000/demo.1\n- Nowak, B. (2019). Wyszukiwanie w bazach dziedzinowych. *Przegląd Biblioteczny*, 8(1), 5–19. https://doi.org/10.0000/demo.2",
        "**Source list (catalogue format)**\n\n- Smith, A. (2021). Methods of literature review. *Information Studies*, 12(3), 45–60. https://doi.org/10.0000/demo.1\n- Brown, B. (2019). Searching subject databases. *Library Review*, 8(1), 5–19. https://doi.org/10.0000/demo.2",
    )
    summary_b = L(
        "**Podsumowanie (format rozmowy)**\n\nKowalska (2021) opisuje metody przeglądu literatury, a Nowak (2019) pokazuje, jak przeszukiwać bazy dziedzinowe.",
        "**Summary (conversation format)**\n\nSmith (2021) describes methods of literature review, and Brown (2019) shows how to search subject databases.",
    )
    refs_items = _cards([("R1", L("Kowalska (2021), Studia Informacyjne", "Smith (2021), Information Studies")),
                         ("R2", L("Nowak (2019), Przegląd Biblioteczny", "Brown (2019), Library Review")),
                         ("R3", L("Kowalska (2012), Studia Informacyjne", "Smith (2012), Information Studies")),
                         ("R4", L("Zieliński (2020), Rocznik Wiedzy", "Green (2020), Knowledge Yearbook")),
                         ("R5", L("Nowak (2019), Rocznik Wiedzy", "Brown (2019), Knowledge Yearbook")),
                         ("R6", L("Wiśniewska (2018), Kwartalnik Metod", "White (2018), Methods Quarterly")),
                         ("R7", L("Kamińska (2022), Zeszyty Danych", "Black (2022), Data Papers"))])
    variant = {"items": refs_items, "design": "v7_k3_lambda1", "reference_order": [["R1", "R2"], ["R3", "R5"], ["R4", "R6", "R7"]]}
    return _bundle(L("Pokaz: eksperyment w ankiecie", "Demonstration: an experiment inside a survey"),
                   L("Losowy przydział do formatu pomocy, wybór formatu i zadanie oceny źródeł.", "Random assignment to an aid format, a free choice of format, and a source-judgement task."), [
        {"key": "consent", "type": "consent", "text": CONSENT},
        {"key": "context", "type": "form", "title": L("O Tobie", "About you"), "questions": [
            {"name": "level", "type": "radio", "required": True, "label": L("Na jakim etapie studiów jesteś?", "Which stage of study are you at?"),
             "options": [{"value": "ma", "label": L("studia magisterskie", "master's studies")}, {"value": "phd", "label": L("szkoła doktorska", "doctoral school")}]},
            {"name": "field", "type": "select", "required": True, "label": L("Dziedzina", "Field"),
             "options": [{"value": "hum", "label": L("nauki humanistyczne", "humanities")}, {"value": "sci", "label": L("nauki ścisłe i przyrodnicze", "exact and natural sciences")}]},
            {"name": "thesis_lang", "type": "radio", "required": False, "label": L("W jakim języku piszesz pracę?", "In which language do you write your thesis?"),
             "options": [{"value": "pl", "label": L("po polsku", "Polish")}, {"value": "en", "label": L("po angielsku", "English")}, {"value": "other", "label": L("w innym", "another")}],
             "condition": {"answer": "level", "op": "eq", "value": "phd"}},
        ]},
        {"key": "arm", "type": "randomizer", "arms": [{"code": "A"}, {"code": "B"}, {"code": "C"}], "strata_by": ["level", "field"]},
        {"key": "aid", "type": "stimulus", "title": L("Materiał pomocniczy", "Aid"), "arm_of": "arm",
         "prompt": L("Przeczytaj materiał. Przyda się w następnym zadaniu.", "Read the material. It will help with the next task."),
         "contents": {"A": {"*": summary_a}, "B": {"*": summary_b}}},
        {"key": "aid_choice", "type": "choice", "title": L("Wybierz materiał", "Choose the material"),
         "prompt": L("Który materiał chcesz zobaczyć przed zadaniem?", "Which material would you like to see before the task?"),
         "condition": {"arm": "arm", "op": "eq", "value": "C"},
         "options": [{"value": "A", "label": L("lista źródeł", "source list"), "preview": L("pełne opisy i DOI", "full records and DOIs")},
                     {"value": "B", "label": L("podsumowanie", "summary"), "preview": L("krótki tekst w formie rozmowy", "a short text in conversation style")}],
         "contents": {"A": {"*": summary_a}, "B": {"*": summary_b}}},
        {"key": "judge", "type": "tap_blocks", "title": L("Ocena źródeł", "Judging sources"),
         "instructions": L("Na każdym ekranie dotknij źródeł po kolei: najpierw tego, które z największą pewnością uważasz za prawdziwe i poprawnie opisane, na końcu tego, które budzi najwięcej wątpliwości.",
                           "On every screen tap the sources from the one you are most sure is genuine and accurate to the one you doubt most."),
         "criterion": L("Ułóż źródła od najbardziej do najmniej wiarygodnego.", "Order the sources from the most to the least trustworthy."),
         "panel_from": ["aid", "aid_choice"],
         "variants_by": "field", "variants": {"hum": variant, "sci": variant},
         "gate": {"question": L("Czy masz pewność co do tej odpowiedzi?", "Were you sure about this block?"),
                  "options": [{"value": "yes", "label": L("tak", "yes")}, {"value": "no", "label": L("nie", "no")}]}},
        {"key": "debrief", "type": "debrief", "text": L(
            "Dziękujemy. W zadaniu dwa źródła były poprawne, dwa zawierały błąd (rok lub czasopismo), a trzy były zmyślone. Materiały pomocnicze przydzielano losowo albo według Twojego wyboru.",
            "Thank you. In the task two sources were correct, two contained an error (year or journal) and three were invented. The aids were assigned at random or by your choice.")},
        {"key": "thanks", "type": "thanks", "text": THANKS},
    ])


def all_demos() -> list[tuple[str, dict[str, Any]]]:
    out = [(f"board-{k}", board_demo(k)) for k in ("tier", "tier_aside", "arrow", "pile", "plane", "pairs")]
    out += [("sob", sob_demo()), ("tap", tap_demo()), ("experiment", experiment_demo())]
    return out
