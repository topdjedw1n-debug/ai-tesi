"""Open-access full text and page-anchored windows per section (S2 material)."""

import asyncio

import httpx
import pytest

from app.services import full_text_sources
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.full_text_sources import (
    DOCUMENT_EVIDENCE_CHARS,
    MIN_RELEVANCE,
    SECTION_EVIDENCE_CHARS,
    attach_full_text,
    document_windows,
    full_text,
    open_access_link,
    open_access_url,
    render_windows,
    section_evidence,
    section_queries,
)
from app.services.source_evidence import evidence_text, freeze_evidence
from app.services.uploaded_sources import split_passages
from tests.test_uploaded_sources import _make_pdf


def test_open_access_url_comes_only_from_provider_open_access_fields():
    work = {
        "best_oa_location": {"pdf_url": "https://x.org/a.pdf"},
        "open_access": {"oa_url": "https://x.org/landing"},
    }
    assert open_access_url(work, "openalex") == "https://x.org/a.pdf"
    assert (
        open_access_url({"open_access": {"oa_url": "https://x.org/l"}}, "openalex")
        == "https://x.org/l"
    )
    assert (
        open_access_url(
            {"openAccessPdf": {"url": "http://s2/p.pdf"}}, "semantic_scholar"
        )
        == "http://s2/p.pdf"
    )
    assert open_access_url({"link": [{"URL": "https://pub/x.pdf"}]}, "crossref") is None
    assert (
        open_access_url({"openAccessPdf": {"url": "ftp://no"}}, "semantic_scholar")
        is None
    )
    row = {"canonical_metadata": {"open_access_url": "https://x.org/a.pdf"}}
    assert open_access_link(row) == "https://x.org/a.pdf"
    assert open_access_link({"canonical_metadata": None}) is None
    assert open_access_link(SourceDoc(title="t", authors=[], year=2020)) is None


def mock_client(monkeypatch, handler):
    original = httpx.AsyncClient

    def factory(**kwargs):
        return original(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(full_text_sources.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_full_text_reads_pdf_follows_citation_meta_and_reports_refusals(
    monkeypatch,
):
    pdf = _make_pdf(["Pagina uno con testo sufficiente " * 8, "Pagina due " * 20])
    landing = (
        b'<html><head><meta name="citation_pdf_url" content="/files/paper.pdf"/>'
        b"</head><body>citation_pdf_url</body></html>"
    )

    def handler(request):
        path = request.url.path
        if path.endswith("direct.pdf") or path == "/files/paper.pdf":
            return httpx.Response(
                200, content=pdf, headers={"content-type": "application/pdf"}
            )
        if path == "/landing":
            return httpx.Response(
                200, content=landing, headers={"content-type": "text/html"}
            )
        if path == "/wall":
            return httpx.Response(403, content=b"<html>Cloudflare</html>")
        if path == "/scan.pdf":
            return httpx.Response(200, content=_make_pdf(["", ""]))
        return httpx.Response(200, content=b"<html>no pdf here</html>")

    mock_client(monkeypatch, handler)
    direct = await full_text("https://repo.test/direct.pdf")
    assert direct["reason"] is None and len(direct["pages"]) == 2
    assert "Pagina uno" in direct["pages"][0]
    hopped = await full_text("https://repo.test/landing")
    assert hopped["final_url"] == "https://repo.test/files/paper.pdf"
    assert len(hopped["pages"]) == 2
    assert (await full_text("https://repo.test/wall"))["reason"] == "http_403"
    assert (await full_text("https://repo.test/other"))["reason"] == "not_pdf"
    assert (await full_text("https://repo.test/scan.pdf"))["reason"] == "no_text_layer"
    monkeypatch.setattr(full_text_sources, "MAX_SOURCE_FILE_BYTES", 16)
    assert (await full_text("https://repo.test/direct.pdf"))["reason"] == "too_large"


def test_document_windows_keep_document_order_and_merge_without_duplicates():
    page = " ".join(f"parola{i}" for i in range(400))
    windows = document_windows(
        "Kabc", "https://repo.test/a.pdf", [page, "Seconda pagina breve."]
    )
    assert len(windows) > 3 and all(w.source_file_id == 0 for w in windows)
    assert [w.page_number for w in windows][-1] == 2
    first_page = [w for w in windows if w.page_number == 1]
    rendered = render_windows(list(enumerate(first_page)))
    assert rendered == "[page 1] " + page
    # Non-adjacent windows stay separate blocks, each with its page label.
    two = render_windows([(0, first_page[0]), (2, first_page[2])])
    assert two.count("[page 1] ") == 2


def pack_with(*rows, passages=None, uploaded=()):
    sources = []
    for key, title, abstract, url in rows:
        source = SourceDoc(
            title=title,
            authors=["Rossi, Maria"],
            year=2024,
            abstract=abstract,
            doi=None if key in uploaded else f"10.1/{key}",
            paper_id=f"uploaded:{key}" if key in uploaded else None,
            provider="uploaded" if key in uploaded else "openalex",
            canonical_metadata={"open_access_url": url} if url else {},
        )
        freeze_evidence(source, passages or [], key, query=title)
        sources.append(PackedSource(source, key, 1.0))
    return SourcePack(1, "controllo a distanza", sources=sources, passages=passages)


def test_section_evidence_planned_windows_then_relevant_documents():
    law_pages = [
        "Art. 4. Gli impianti audiovisivi e gli altri strumenti di controllo a distanza "
        "dei lavoratori possono essere impiegati per esigenze organizzative. " * 6,
        "Comma 3. Le informazioni raccolte sono utilizzabili a tutti i fini connessi al "
        "rapporto di lavoro a condizione che sia data adeguata informazione. " * 6,
    ]
    off_topic = ["Analisi dei ponti ad arco e rilievi geodetici della struttura. " * 12]
    passages = document_windows("KLAW", "https://norm.test/art4", law_pages)
    passages += document_windows("KBRIDGE", "https://eng.test/bridge", off_topic)
    passages += document_windows(
        "KPLAN", "https://doc.test/plan", ["Testo del piano. " * 30]
    )
    # A fetched open-access article that S3 did not plan joins the section when
    # its best window covers the section's own wording (the same gate as an
    # upload): no section is written from abstracts while a document exists.
    passages += document_windows("KOAOFF", "u", law_pages)
    pack = pack_with(
        (
            "KPLAN",
            "Controllo a distanza",
            "Anteprima del documento pianificato.",
            "https://doc.test/plan",
        ),
        ("KABS", "Solo abstract", "Il datore di lavoro e la privacy.", None),
        (
            "KLAW",
            "Statuto dei lavoratori art. 4",
            "Impianti audiovisivi e strumenti di controllo.",
            "https://norm.test/art4",
        ),
        ("KBRIDGE", "Ponti ad arco", "Rilievi geodetici.", "https://eng.test/bridge"),
        ("KOAOFF", "Articolo aperto", "Controllo a distanza dei lavoratori.", "u"),
        passages=passages,
        uploaded=("KLAW", "KBRIDGE", "KPLAN"),
    )
    section = {
        "title": "Il controllo a distanza dei lavoratori",
        "purpose": "Presupposti dell'art. 4",
        "main_points": [
            "Impianti audiovisivi e strumenti di controllo",
            "Utilizzabilità delle informazioni raccolte",
        ],
        "scope_ids": ["scope-1"],
        "evidence_keys": ["KPLAN", "KABS", "KMISSING"],
    }
    nodes = [
        {
            "scope_id": "scope-1",
            "terms_local": ["controllo a distanza"],
            "terms_en": ["remote monitoring"],
        }
    ]
    queries = section_queries(section, nodes)
    assert len(queries) == 2 and queries[1] == "remote monitoring"
    assert "controllo a distanza" in queries[0] and "remote" not in queries[0]
    items, report = section_evidence(pack, section, nodes)
    # Documents with relevant windows come first, most relevant first; the
    # off-topic upload fails the gate on the section's own wording.
    assert [i["key"] for i in items] == ["KLAW", "KOAOFF", "KPLAN", "KABS"]
    law = report[0]
    assert law["planned"] is False and law["score"] >= MIN_RELEVANCE
    assert (
        law["pages"] == [1] and law["gap"] is False
    )  # page 2 is below the relative floor
    assert items[0]["text"].startswith("[page 1] Art. 4.")
    assert "KBRIDGE" not in [i["key"] for i in items]
    # A planned full-text document without a relevant window keeps its frozen
    # excerpt (never less than before) and is reported as a gap.
    assert items[2]["text"] == evidence_text(pack.by_key("KPLAN").source)
    assert report[2]["windows"] == 0 and report[2]["gap"] is True
    # Abstract-only evidence keeps the frozen excerpt exactly as before.
    assert items[3]["text"] == evidence_text(pack.by_key("KABS").source)
    assert report[3] == {
        "key": "KABS",
        "planned": True,
        "windows": 0,
        "pages": [],
        "chars": len(items[3]["text"]),
        "score": 0.0,
        "gap": False,
        "capped": False,
    }
    assert sum(r["chars"] for r in report) <= SECTION_EVIDENCE_CHARS + 2400
    # Without any full text the shape is the historical one: planned keys, excerpts.
    plain = pack_with(
        ("KA", "A", "Abstract A.", None), ("KB", "B", "Abstract B.", None)
    )
    items, report = section_evidence(
        plain, {**section, "evidence_keys": ["KB", "KA"]}, nodes
    )
    assert items == [
        {"key": "KB", "text": "Abstract B."},
        {"key": "KA", "text": "Abstract A."},
    ]
    assert not any(r["windows"] for r in report)


def test_section_evidence_shares_the_budget_round_robin(monkeypatch):
    statute = ["Controllo a distanza dei lavoratori: impianti audiovisivi. " * 6]
    judgment = [
        f"Punto {n}. La Corte osserva che il controllo a distanza dei lavoratori "
        "richiede impianti audiovisivi autorizzati. " * 6
        for n in range(1, 13)
    ]
    passages = document_windows("KSTATUTE", "u1", statute)
    passages += document_windows("KJUDGMENT", "u2", judgment)
    pack = pack_with(
        ("KSTATUTE", "Statuto", "Norma.", "u1"),
        ("KJUDGMENT", "Sentenza", "Decisione.", "u2"),
        passages=passages,
    )
    section = {
        "title": "Il controllo a distanza dei lavoratori",
        "purpose": "impianti audiovisivi",
        "main_points": [],
        "scope_ids": [],
        "evidence_keys": ["KJUDGMENT", "KSTATUTE"],
    }
    monkeypatch.setattr(full_text_sources, "RELATIVE_FLOOR", 0.0)
    monkeypatch.setattr(full_text_sources, "SECTION_EVIDENCE_CHARS", 3000)
    items, report = section_evidence(pack, section, [])
    # The one-window statute is not starved by the judgment's many windows.
    assert [r["key"] for r in report] == ["KJUDGMENT", "KSTATUTE"]
    assert report[0]["windows"] >= 1 and report[1]["windows"] == 1
    assert sum(r["chars"] for r in report) <= 3000
    monkeypatch.setattr(full_text_sources, "SECTION_EVIDENCE_CHARS", 20_000)
    monkeypatch.setattr(full_text_sources, "DOCUMENT_EVIDENCE_CHARS", 2000)
    items, report = section_evidence(pack, section, [])
    assert report[0]["chars"] <= 2000 + 10 and report[0]["windows"] >= 2
    assert DOCUMENT_EVIDENCE_CHARS == 16_000


@pytest.mark.asyncio
async def test_attach_full_text_extends_passages_and_reports_failures(monkeypatch):
    pages = [
        "Controllo a distanza dei lavoratori e privacy. " * 12,
        "Seconda pagina utile. " * 12,
    ]

    async def fake_full_text(url):
        if url.endswith("ok.pdf"):
            return {"url": url, "final_url": url, "pages": pages, "reason": None}
        if url.endswith("wall"):
            return {"url": url, "final_url": url, "pages": [], "reason": "http_403"}
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(full_text_sources, "full_text", fake_full_text)
    pack = pack_with(
        ("KOK", "Controllo a distanza", "Sintesi.", "https://r.test/ok.pdf"),
        ("KWALL", "Dietro il muro", "Sintesi.", "https://r.test/wall"),
        ("KDOWN", "Rete assente", "Sintesi.", "https://r.test/down"),
        ("KNONE", "Senza link", "Sintesi.", None),
    )
    passages = []
    summary, unavailable = await attach_full_text(
        pack.sources, passages, asyncio.Semaphore(2), "controllo a distanza"
    )
    assert [s["key"] for s in summary] == ["KOK", "KWALL", "KDOWN"]
    assert unavailable == ["KWALL", "KDOWN"]
    assert summary[2]["reason"] == "transport_error"
    assert {p.citation_key for p in passages} == {"KOK"} and len(passages) >= 2
    ok = pack.by_key("KOK").source.canonical_metadata
    assert ok["evidence_level"] == "pdf" and ok["full_text"]["pages"] == 2
    assert ok["full_text"]["windows"] == len(passages)
    excerpt = evidence_text(pack.by_key("KOK").source)
    assert excerpt.startswith("Sintesi.\n[page ") and len(excerpt) <= 2400
    assert "full_text" not in pack.by_key("KWALL").source.canonical_metadata


def test_split_passages_windows_are_the_fragment_unit():
    windows = split_passages(
        source_file_id=0, citation_key="K", filename="u", pages=[(1, "a b c " * 400)]
    )
    assert len(windows) > 1 and all(len(w.text) <= 1000 for w in windows)


def test_section_evidence_keeps_at_most_four_documents_by_relevance():
    from app.services.section_material import MAX_SECTION_DOCUMENTS

    text = "Controllo a distanza dei lavoratori e impianti audiovisivi. " * 6
    passages = []
    specs = []
    for n in range(6):
        key = f"KDOC{n}"
        # Later documents repeat the section wording more often: more relevant.
        passages += document_windows(key, f"u{n}", [text + "impianti " * n])
        specs.append((key, f"Documento {n}", "Sintesi.", f"u{n}"))
    pack = pack_with(*specs, passages=passages)
    section = {
        "title": "Il controllo a distanza dei lavoratori",
        "purpose": "impianti audiovisivi",
        "main_points": [],
        "scope_ids": [],
        "evidence_keys": [f"KDOC{n}" for n in range(6)],
    }
    items, report = section_evidence(pack, section, [])
    windowed = [r for r in report if r["windows"]]
    # Six academic documents: only MAX_ACADEMIC_DOCUMENTS carry windows.
    from app.services.section_material import MAX_ACADEMIC_DOCUMENTS

    assert len(windowed) == MAX_ACADEMIC_DOCUMENTS == 2 and MAX_SECTION_DOCUMENTS == 4
    # The planned documents below the cap keep their excerpts, marked capped.
    rest = [r for r in report if not r["windows"]]
    assert len(rest) == 4 and all(r["capped"] and not r["gap"] for r in rest)
    assert [i["text"] for i in items[2:]] == [
        evidence_text(pack.by_key(r["key"]).source) for r in rest
    ]


def test_catalogue_limits_follow_the_provider_settings():
    from app.core.config import settings
    from app.services.ai_pipeline.rag_retriever import _catalogue_limits

    assert _catalogue_limits("https://api.openalex.org/works?search=x") == (
        "openalex",
        settings.OPENALEX_RATE_LIMIT_RPS,
    )
    assert _catalogue_limits("https://api.crossref.org/works")[0] == "crossref"
    assert _catalogue_limits("https://export.arxiv.org/api/query") == (
        "arxiv",
        settings.ARXIV_RATE_LIMIT_RPS,
    )
    assert _catalogue_limits("https://api.semanticscholar.org/graph/v1/x")[0] == (
        "semantic_scholar"
    )


def test_primary_sources_lead_and_commentary_is_rationed_across_the_work():
    from app.services.section_material import commentary_budget

    text = "Controllo a distanza dei lavoratori e impianti audiovisivi. " * 6
    passages = document_windows("KLAW", "u1", [text])
    passages += document_windows("KDOC", "u2", [text + "commento dottrinale "])
    passages += document_windows("KOTHER", "u3", [text + "altro commento "])
    pack = pack_with(
        ("KDOC", "Commento alla disciplina", "Sintesi.", "u2"),
        ("KLAW", "Legge 20 maggio 1970, n. 300, art. 4", "Norma.", "u1"),
        ("KOTHER", "Altro commento", "Sintesi.", "u3"),
        passages=passages,
    )
    section = {
        "title": "Il controllo a distanza dei lavoratori",
        "purpose": "impianti audiovisivi",
        "main_points": [],
        "scope_ids": [],
        "evidence_keys": ["KDOC", "KLAW", "KOTHER"],
    }
    # The statute comes first whatever the plan order; commentary follows.
    items, report = section_evidence(pack, section, [])
    assert [r["key"] for r in report if r["windows"]][0] == "KLAW"
    # A commentary document may carry windows in a third of the sections only:
    # with a three-section plan that is one section, then it keeps its excerpt.
    budget = commentary_budget([{}, {}, {}])
    first = section_evidence(pack, section, [], commentary=budget)[1]
    second = section_evidence(pack, section, [], commentary=budget)[1]
    assert budget["cap"] == 1
    assert [r["key"] for r in first if r["windows"]] == ["KLAW", "KDOC", "KOTHER"]
    assert [r["key"] for r in second if r["windows"]] == ["KLAW"]
    assert all(r["capped"] for r in second if r["key"] != "KLAW")
