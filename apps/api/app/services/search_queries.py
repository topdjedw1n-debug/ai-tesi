"""Topic-anchored catalogue queries for S2 and the on-topic filter for candidates.

15.09.2026, works without manager PDFs: the scope terms of structural nodes
("introduzione", "metodologia", "bibliografia") and of sub-nodes ("engagement",
"best practice") went to the catalogues as they were and the pack came back
off-topic (tourism, museums, pedagogy, "Copper complexes of synthetic
peptides"). Now every query carries the core of the topic, nodes without a
literature of their own are not searched, chapters are covered through their
sub-nodes, and a candidate without a topic word in its title or abstract is
dropped before verification (which also spares the catalogues' quotas).
"""

import re
from collections import Counter

STRUCTURAL = {
    "introduzione",
    "introduction",
    "premessa",
    "conclusioni",
    "conclusione",
    "conclusion",
    "conclusions",
    "bibliografia",
    "bibliography",
    "references",
    "riferimenti",
    "riferimenti bibliografici",
    "sitografia",
    "indice",
    "sommario",
    "abstract",
    "ringraziamenti",
    "appendice",
    "appendix",
    "allegati",
}
STOPWORDS = set(
    "il lo la i gli le l un uno una di del dello della dei degli delle da dal dallo "
    "dalla dai dagli dalle a al allo alla ai agli alle in nel nello nella nei negli "
    "nelle su sul sullo sulla sui sugli sulle con per tra fra e ed o od che chi cui "
    "non si sono è sua suo sue suoi come più anche ma se ne ci vi lo the a an of "
    "and or in on at to for from by with as is are be its their this that these "
    "those into onto via vs versus between among through under over".split()
)
GENERIC = set(
    "analisi studio studi ruolo aspetti profili approccio approcci confronto "
    "strategia strategie sistema sistemi caso casi quadro teorico teorica "
    "evoluzione sviluppo metodologia metodologie metodo metodi evidenze empirica "
    "empiriche empirico letteratura rassegna panoramica prospettive prospettiva "
    "obiettivi obiettivo domande ricerca risultati discussione implicazioni "
    "definizione concetto concetti nozione nozioni fondamenti principi problema "
    "problemi tema temi tesi elaborato lavoro capitolo sezione paragrafo "
    "italia italiana italiane italiano italiani italy italian europa europea "
    "europeo european europe internazionale nazionale basati basato basate "
    "research study studies analysis role approach approaches framework theory "
    "theoretical empirical evidence methodology methods method literature review "
    "overview perspectives objectives questions results discussion implications "
    "definition concept concepts fundamentals principles problem issues topic "
    "chapter section case cases comparison strategies strategy systems system "
    "based selection best practice practices future limitations".split()
)
WORD = re.compile(r"[^\W_][\w'\-]*")  # Unicode letters: Bărbulescu stays one word
NUMBERING = re.compile(
    r"^\s*(?:capitolo|chapter|parte)?\s*[\divx]+(?:\.\d+)*[.)\s:–-]+", re.I
)
MAX_TOKENS = 12


def tokens(text):
    return [t for t in WORD.findall(text.casefold()) if t not in STOPWORDS]


def content_tokens(text):
    return [t for t in tokens(text) if len(t) >= 3 and t not in GENERIC]


def is_structural(node):
    title = NUMBERING.sub("", node.get("title") or "").strip().casefold()
    words = title.split()
    return title in STRUCTURAL or bool(words) and words[0] in STRUCTURAL


def topic_core(topic, limit=4):
    main = topic.split(":")[0]
    return list(dict.fromkeys(t for t in content_tokens(main) if len(t) >= 4))[:limit]


def proper_names(topic):
    """Capitalised words inside the title or its subtitle, lower-cased.

    24.09.2026, order 24286128: "Spazi, silenzi e relazioni: lo sguardo di
    Michelangelo Antonioni sull'incomunicabilità" - the subject named after
    the colon never reached a query (0 of 48 carried "Antonioni") and the
    catalogues answered on "spazi silenzi relazioni" (city pedagogy,
    Kierkegaard). The first word of the title and of the subtitle is
    capitalised by position, not by name, and does not count.
    """
    names = []
    for part in topic.split(":"):
        for word in WORD.findall(part)[1:]:
            token = word.casefold()
            if word[0].isupper() and token in content_tokens(word):
                names.append(token)
    return list(dict.fromkeys(names))


def english_core(nodes, limit=4):
    counter = Counter()
    for node in walk(nodes):
        if not is_structural(node):
            counter.update(
                t for t in dict.fromkeys(content_tokens(" ".join(node["terms_en"])))
            )
    return [t for t, _ in counter.most_common(limit)]


def walk(nodes, parent=None):
    for node in nodes:
        yield node
        yield from walk(node.get("children", []), node)


def query(core, terms):
    words = list(dict.fromkeys(core + tokens(" ".join(terms))))
    return " ".join(words[:MAX_TOKENS])


def plan(topic, nodes):
    """(scope_id, query) pairs, the parent of every scope and the anchors.

    Chapters with sub-nodes are not searched themselves: their sub-nodes carry
    the specific questions, and the hits are attributed to the chapter too.
    """
    names = proper_names(topic)
    core_local = list(dict.fromkeys(names + topic_core(topic)))[:4]
    core_en = list(dict.fromkeys(names + english_core(nodes)))[:4]
    requests, parents = [], {}

    def visit(items, parent):
        for node in items:
            if parent is not None:
                parents[node["scope_id"]] = parent["scope_id"]
            children = node.get("children", [])
            if is_structural(node):
                continue
            if children:
                visit(children, node)
                continue
            for text in dict.fromkeys(
                (
                    query(core_local, node["terms_local"]),
                    query(core_en, node["terms_en"]),
                )
            ):
                requests.append((node["scope_id"], text))

    visit(nodes, None)
    return requests, parents, anchors(topic, english_core(nodes, 8))


def anchors(topic, core_en=()):
    """Word starts that mark a candidate as being about the topic."""
    words = list(dict.fromkeys(content_tokens(topic) + list(core_en)))
    parts = [re.escape(w[:6]) if len(w) >= 6 else re.escape(w) + r"\b" for w in words]
    return re.compile(r"\b(?:" + "|".join(parts) + ")") if parts else None


def on_topic(row, pattern):
    """A candidate stays with two different topic words in title or abstract;
    without an abstract one word in the title is enough (too little is known
    to call it off-topic). A single generic hit ("sociale", "digitale") is not."""
    if not row.get("title"):
        return False
    if pattern is None:
        return True
    title, abstract = row["title"].casefold(), (row.get("abstract") or "").casefold()
    found = {m.group(0) for m in pattern.finditer(f"{title} {abstract}")}
    return len(found) >= 2 or (not abstract and bool(pattern.search(title)))
