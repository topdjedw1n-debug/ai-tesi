"""The S4 laboratory's own boundaries: pricing, ceiling, secrets, network."""

import importlib.util
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "s4_lab", Path(__file__).parents[1] / "scripts/s4_lab.py"
)
lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lab)
PRICING_INPUT = {"anthropic": {"claude-opus-4-8": 5.0}}
PRICING_OUTPUT = {"anthropic": {"claude-opus-4-8": 25.0}}


def args(**values):
    defaults = {"price_input_usd_per_1m": None, "price_output_usd_per_1m": None}
    return SimpleNamespace(**{**defaults, **values})


def test_instruction_and_sections_helpers():
    assert lab.normalize_instruction("Write.\n\n") == "\nWrite.\n"
    assert lab.parse_sections("5, 6") == {5, 6} and lab.parse_sections("") is None
    with pytest.raises(ValueError):
        lab.parse_sections("0")


def test_secrets_are_limited_to_provider_keys(tmp_path):
    path = tmp_path / "env"
    path.write_text(
        'DATABASE_URL=postgres://real\nexport ANTHROPIC_API_KEY="sk-ant-x"\n'
        "OPENALEX_API_KEY=oa\n# SEMANTIC_SCHOLAR_API_KEY=commented\n"
    )
    assert lab.read_secrets(path, {"SEMANTIC_SCHOLAR_API_KEY": "s2"}) == {
        "ANTHROPIC_API_KEY": "sk-ant-x",
        "OPENALEX_API_KEY": "oa",
        "SEMANTIC_SCHOLAR_API_KEY": "s2",
    }


def test_prices_production_first_then_lab_then_explicit():
    assert lab.resolve_prices(
        "claude-opus-4-8", args(), PRICING_INPUT, PRICING_OUTPUT
    ) == (
        (5.0, 25.0),
        False,
    )
    assert lab.resolve_prices(
        "claude-opus-5", args(), PRICING_INPUT, PRICING_OUTPUT
    ) == (
        (5.0, 25.0),
        True,
    )
    explicit = args(price_input_usd_per_1m=1.0, price_output_usd_per_1m=2.0)
    assert lab.resolve_prices("x", explicit, PRICING_INPUT, PRICING_OUTPUT) == (
        (1.0, 2.0),
        True,
    )
    with pytest.raises(SystemExit):
        lab.resolve_prices("x", args(), PRICING_INPUT, PRICING_OUTPUT)
    assert not set(lab.LAB_PRICING_USD_PER_1M) & set(PRICING_INPUT["anthropic"])


def test_ledger_checks_ceiling_before_each_call_and_keeps_failures():
    ledger = lab.Ledger(0.5, lambda model: (5.0, 25.0), 4)
    request = {"model": "m", "max_tokens": 4000, "messages": [{"content": "x" * 4000}]}
    assert ledger.check(request, "S4", 5) == pytest.approx(0.105)
    response = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=1000, output_tokens=1000),
        stop_reason="end_turn",
        id="msg",
    )
    ledger.add(response, request, "S4", 5, 1.0)
    assert ledger.spent_usd == pytest.approx(0.03)
    ledger.add_failure(TimeoutError("late"), request, "S4", 5, 2.0)
    assert ledger.unknown_spend_usd == pytest.approx(0.105)
    assert [c["outcome"] for c in ledger.calls] == ["received", "failed"]
    big = {**request, "max_tokens": 16000}
    with pytest.raises(lab.CostCapExceeded):
        ledger.check(big, "S6", None)


def test_network_guard_refuses_unknown_hosts_and_patches_as_functions():
    guard = lab.NetworkGuard({"api.anthropic.com"})
    with pytest.raises(socket.gaierror):
        guard.getaddrinfo("example.invalid", 443)
    with pytest.raises(ConnectionRefusedError):
        guard.connect(object(), ("203.0.113.9", 443))
    assert guard.refused == ["example.invalid", "203.0.113.9"]
    patches = guard.patches()
    assert [p.attribute for p in patches] == ["getaddrinfo", "connect"]
    # The class-level connect must receive the socket instance, unlike a bound method.
    with patches[1]:
        with pytest.raises(ConnectionRefusedError):
            socket.socket().connect(("203.0.113.9", 443))


def test_writer_request_and_override_parsing():
    request = {"model": "claude-opus-4-8", "max_tokens": 10, "messages": []}
    assert lab.writer_request(request, None, None) == request
    changed = lab.writer_request(
        request, "claude-opus-5", {"thinking": {"type": "disabled"}}
    )
    assert changed["model"] == "claude-opus-5" and changed["max_tokens"] == 10
    assert (
        changed["thinking"] == {"type": "disabled"} and request.get("thinking") is None
    )
    assert lab.parse_override(None) is None
    assert lab.parse_override('{"thinking": {"type": "disabled"}}') == {
        "thinking": {"type": "disabled"}
    }
    for bad in ("[]", "{}", '{"model": "x"}', '{"max_tokens": 5}'):
        with pytest.raises(ValueError):
            lab.parse_override(bad)


def test_section_evidence_and_instruction_swap(tmp_path):
    path = tmp_path / "ev.json"
    path.write_text(
        json.dumps(
            {
                "20": {
                    "add": [
                        {
                            "key": "NORM.ART4",
                            "title": "t",
                            "authors": ["a"],
                            "year": 2015,
                            "text": "x" * 10,
                        }
                    ]
                }
            }
        )
    )
    loaded = lab.load_section_evidence(path)
    assert list(loaded) == [20] and loaded[20][0]["key"] == "NORM.ART4"
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "1": {
                    "add": [
                        {
                            "key": "K",
                            "title": "t",
                            "authors": [],
                            "year": 1,
                            "text": "y" * 2401,
                        }
                    ]
                }
            }
        )
    )
    with pytest.raises(ValueError):
        lab.load_section_evidence(bad)
    request = {
        "model": "m",
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "HEAD\nPROD\nJSON PROD"}],
    }
    swapped = lab.with_instruction(request, "PROD", "VAR")
    assert swapped["messages"][0]["content"] == "HEAD\nVAR\nJSON PROD"
    assert request["messages"][0]["content"] == "HEAD\nPROD\nJSON PROD"


def test_uploaded_sources_spec_is_validated_and_parsed_by_production_code(tmp_path):
    from tests.test_uploaded_sources import _make_pdf

    pdf = tmp_path / "norma.pdf"
    pdf.write_bytes(_make_pdf(["Articolo 4 comma 1 testo " * 20, "Comma 2 " * 30]))
    spec = tmp_path / "uploads.json"
    spec.write_text(
        json.dumps(
            [
                {
                    "pdf": "norma.pdf",
                    "key": "ART4",
                    "title": "Statuto, art. 4",
                    "authors": ["Repubblica Italiana"],
                    "year": 1970,
                    "mandatory": True,
                }
            ]
        )
    )
    specs = lab.load_uploaded_sources(spec)
    rows, passages, report = lab.uploaded_inputs(specs, tmp_path)
    assert rows[0]["key"] == "ART4" and rows[0]["verification_status"] == "verified"
    assert rows[0]["source"]["paper_id"] == "uploaded:900001"
    assert {p["citation_key"] for p in passages} == {"ART4"}
    assert {p["page_number"] for p in passages} == {1, 2}
    assert report[0]["pages"] == 2 and report[0]["windows"] == len(passages)
    assert lab.load_uploaded_sources(None) == []
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            [{"pdf": "norma.pdf", "key": "A:1", "title": "t", "authors": [], "year": 1}]
        )
    )
    with pytest.raises(ValueError):
        lab.load_uploaded_sources(bad)
    missing = tmp_path / "missing.json"
    missing.write_text(
        json.dumps(
            [{"pdf": "nope.pdf", "key": "A", "title": "t", "authors": [], "year": 1}]
        )
    )
    with pytest.raises(ValueError):
        lab.load_uploaded_sources(missing)
