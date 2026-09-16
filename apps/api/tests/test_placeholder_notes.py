"""Placeholders by context: verification notes about the material and bare
notes are flagged; ordinary Italian "da verificare" is prose."""

from app.services.executor_v2.budgets import POLICY
from app.services.placeholder_notes import find_placeholders

PHRASES = POLICY["placeholder_phrases"]


def test_ordinary_italian_is_not_a_placeholder():
    for text in (
        # Law runs of 16.09.2026: two false "placeholder_text" warnings.
        "Il coordinamento tra le fonti non è un dato acquisito ma una "
        "costruzione da verificare caso per caso. La Cassazione ammette.",
        "Il comma 3 mantiene ferma la soglia dell'informazione, da verificare "
        "strumento per strumento. L'esenzione riguarda la fase installativa.",
        "La trasferibilità resta, tuttavia, da verificare, poiché la fonte "
        "non affronta direttamente tale ambito.",
        "La legittimità del controllo è soggetta a verifica giudiziale.",
        "Todorov e i todos della lista; la citazione necessaria è presente.",
    ):
        assert find_placeholders(text, PHRASES) == [], text


def test_verification_notes_about_the_material_are_placeholders():
    # Real notes of the recorded work of 09.09.2026 (job12).
    assert find_placeholders(
        "Rimando a manuali e linee guida da verificare [STD:who-thermal].", PHRASES
    ) == ["da verificare"]
    assert find_placeholders(
        "Li tratto come materia da verificare, senza attribuire dati.", PHRASES
    ) == ["da verificare"]
    assert find_placeholders(
        "Materia manualistica soggetta a verifica, dichiarando il gap.", PHRASES
    ) == ["soggetta a verifica"]
    assert find_placeholders("La fonte è SOGGETTA A VERIFICA.", PHRASES) == [
        "soggetta a verifica"
    ]


def test_bare_notes_and_exact_markers_are_placeholders():
    assert find_placeholders("Da   verificare.", PHRASES) == ["da   verificare"]
    assert find_placeholders("Tasso [da verificare] del 3 %.", PHRASES) == [
        "da verificare"
    ]
    assert find_placeholders("Un valore (da verificare) qui.", PHRASES) == [
        "da verificare"
    ]
    assert find_placeholders("Dati sulla mortalità: DA VERIFICARE.", PHRASES) == [
        "da verificare"
    ]
    assert find_placeholders(
        "Fonte [citation needed] e [TODO]: completare.", PHRASES
    ) == ["[citation needed]", "todo"]
