"""
Unit tests for the offline stylometric human-likeness measurer.

These assert the DIRECTION of each confirmed marker (human-uneven prose scores
higher than flat noun-heavy prose), plus graceful handling of short/empty
input. They are not calibration tests — the absolute composite is a heuristic.
"""

from app.services.ai_pipeline.stylometrics import human_likeness

# Flat, noun-heavy, monotone-length prose — the AI profile the research
# describes: low burstiness, high nominalization, no pronouns/auxiliaries.
AI_LIKE_EN = (
    "The implementation of the optimization of the classification system "
    "requires the consideration of the utilization of the computation of the "
    "resources. The evaluation of the performance necessitates the "
    "examination of the quantification of the accuracy of the prediction. "
    "The determination of the configuration demands the identification of the "
    "specification of the requirement of the operation. The realization of "
    "the transformation involves the application of the modification of the "
    "representation of the information."
)

# Human-uneven prose: mixed sentence lengths, verbs, pronouns, auxiliaries.
HUMAN_LIKE_EN = (
    "We ran the model. It worked, though not at first. When we looked closely "
    "at what the classifier was actually doing on the harder cases, we saw "
    "that it kept confusing two categories that any reader would tell apart "
    "in a second. So we changed the features and tried again. This time the "
    "accuracy jumped, and it held up when we tested it on new data. That "
    "surprised us. Why did such a small change matter so much? We think it is "
    "because the old features hid the signal we needed."
)

AI_LIKE_IT = (
    "L'implementazione dell'ottimizzazione della classificazione richiede la "
    "considerazione dell'utilizzazione della computazione delle risorse. La "
    "valutazione della prestazione necessita l'esaminazione della "
    "quantificazione dell'accuratezza della predizione. La determinazione "
    "della configurazione richiede l'identificazione della specificazione "
    "dell'operazione. La realizzazione della trasformazione comporta "
    "l'applicazione della modificazione della rappresentazione "
    "dell'informazione e la definizione della standardizzazione della "
    "documentazione della valutazione."
)

HUMAN_LIKE_IT = (
    "Abbiamo provato il modello. Ha funzionato, ma non subito. Quando siamo "
    "andati a vedere cosa faceva davvero sui casi difficili, ci siamo accorti "
    "che confondeva due categorie che chiunque distinguerebbe in un secondo. "
    "Allora abbiamo cambiato le variabili e ci abbiamo riprovato. Questa "
    "volta ha tenuto. Perché un cambiamento così piccolo conta tanto? Noi "
    "pensiamo che le vecchie variabili nascondessero il segnale."
)


def test_human_prose_scores_higher_than_ai_prose_en():
    ai = human_likeness(AI_LIKE_EN, "en")
    human = human_likeness(HUMAN_LIKE_EN, "en")
    assert human["human_likeness"] > ai["human_likeness"]


def test_human_prose_scores_higher_than_ai_prose_it():
    ai = human_likeness(AI_LIKE_IT, "it")
    human = human_likeness(HUMAN_LIKE_IT, "it")
    assert human["human_likeness"] > ai["human_likeness"]


def test_ai_prose_flags_high_nominalization_low_burstiness():
    ai = human_likeness(AI_LIKE_EN, "en")
    human = human_likeness(HUMAN_LIKE_EN, "en")
    # Noun-heavy AI text has denser nominalization...
    assert ai["nominalization_density"] > human["nominalization_density"]
    # ...and flatter sentence-length variation than the uneven human text.
    assert ai["burstiness_cv"] < human["burstiness_cv"]
    # ...and fewer pronouns.
    assert ai["pronoun_ratio"] < human["pronoun_ratio"]


def test_short_text_returns_none_markers_not_crash():
    result = human_likeness("Too short.", "en")
    # Below the measurement floor: markers are None, nothing raises.
    assert result["human_likeness"] is None
    assert result["nominalization_density"] is None
    assert result["word_count"] == 2


def test_empty_text_is_safe():
    result = human_likeness("", "en")
    assert result["human_likeness"] is None
    assert result["word_count"] == 0
    assert result["sentence_count"] == 0


def test_citations_and_placeholders_do_not_distort_counts():
    # Frozen placeholders (⟦C1⟧) and [Author, Year] markers must be stripped
    # before measuring so they neither inflate word counts nor look like nouns.
    with_markers = (
        "We found a clear effect [Rossi, 2024] and it held ⟦C1⟧ across every "
        "test we ran, which honestly surprised the whole team quite a lot. "
        "So we looked again. The numbers stayed put [Bianchi, 2023]. We could "
        "not explain it at first, but when we traced the pipeline back to the "
        "raw inputs ⟦C2⟧ the reason finally became obvious to all of us."
    )
    result = human_likeness(with_markers, "en")
    # 'C1'/'C2' and bracket contents are excluded from the word set.
    assert result["word_count"] > 0
    assert result["human_likeness"] is not None


def test_composite_is_bounded_0_100():
    for text, lang in [
        (AI_LIKE_EN, "en"),
        (HUMAN_LIKE_EN, "en"),
        (AI_LIKE_IT, "it"),
        (HUMAN_LIKE_IT, "it"),
    ]:
        score = human_likeness(text, lang)["human_likeness"]
        assert 0.0 <= score <= 100.0
