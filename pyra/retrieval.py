"""Find the passages of our papers that answer a question (Prompt 8).

Documents go into an in-memory Index as chunks of a few hundred words, each
with an id like S1 that the assistant cites. Search mixes two scores:

    BM25          keyword match, good at exact terms like "LSP" or "kPa"
    TF-IDF cosine our stand-in for embedding similarity, standard library only

The team chose an in-memory store (config/decisions.json, search_store) and no
installs, so there is no sentence-transformers model. TF-IDF cosine only sees
shared words, not meaning; swap _cosine for real embeddings if that hurts.

.txt and .md files are read directly. Pages are split on form feeds or on
"--- page N ---" lines. PDFs need PyMuPDF (import fitz), which is optional:
without it, reading a PDF raises an error saying so.
"""

import math
import re
from collections import Counter
from pathlib import Path

TOP_K = 6
MIN_WORDS, MAX_WORDS = 300, 500
# Our own choices (DERIVED). Keyword and vector scores count equally.
KEYWORD_WEIGHT = 0.5
# Below this TF-IDF cosine a chunk does not count as context at all.
MIN_SIMILARITY = 0.08
BM25_K1, BM25_B = 1.5, 0.75

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or that the
this to was were what which with how does did do any about into than then there these
those their they we our you your can""".split())

PAGE_MARK = re.compile(r"^-{3}\s*page\s+(\d+)\s*-{3}\s*$", re.IGNORECASE | re.MULTILINE)
HEADING = re.compile(r"^(#{1,6}\s+.+|\d+(\.\d+)*\.?\s+[A-Z][^.]{0,80})$")


def words(text):
    """Lowercase search terms, without stopwords. Decimals like 0.16 stay whole."""
    return [w for w in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower()) if w not in STOPWORDS]


def split_pages(text):
    """[(page number, text)] from form feeds or "--- page N ---" markers."""
    marks = list(PAGE_MARK.finditer(text))
    if marks:
        pages = []
        if text[:marks[0].start()].strip():
            pages.append((None, text[:marks[0].start()]))
        for mark, after in zip(marks, marks[1:] + [None]):
            end = after.start() if after else len(text)
            pages.append((int(mark.group(1)), text[mark.end():end]))
        return pages
    return [(number, page) for number, page in enumerate(text.split("\f"), start=1)]


def read_pages(path):
    """[(page, text)] for a .txt, .md or .pdf file."""
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return split_pages(path.read_text(encoding="utf-8"))
    try:
        import fitz
    except ImportError:
        raise RuntimeError(f"Cannot read {path.name}: PDFs need PyMuPDF (import fitz), "
                           "which is not installed. Save the paper as .txt instead.") from None
    with fitz.open(path) as pdf:
        return [(number, page.get_text()) for number, page in enumerate(pdf, start=1)]


def split_sections(text, section=None):
    """[(section heading, [paragraphs])]. Text before the first heading keeps `section`."""
    sections = [(section, [])]
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
        if lines and HEADING.match(lines[0]):
            sections.append((lines[0].lstrip("#").strip(), []))
            lines = lines[1:]
        if lines:
            sections[-1][1].append(" ".join(lines))
    return [(heading, paragraphs) for heading, paragraphs in sections if paragraphs]


def pack(paragraphs):
    """Join paragraphs into chunks of MIN_WORDS..MAX_WORDS whitespace tokens where possible."""
    chunks, current = [], []
    for paragraph in paragraphs:
        tokens = paragraph.split()
        while len(tokens) > MAX_WORDS:
            if current:
                chunks.append(current)
                current = []
            chunks.append(tokens[:MAX_WORDS])
            tokens = tokens[MAX_WORDS:]
        if current and (len(current) >= MIN_WORDS or len(current) + len(tokens) > MAX_WORDS):
            chunks.append(current)
            current = []
        current = current + tokens
    if current:
        chunks.append(current)
    return [" ".join(tokens) for tokens in chunks]


class Index:
    """Chunks plus the counts BM25 and TF-IDF need. Rebuilt lazily after adds."""

    def __init__(self):
        self.chunks = []
        self._stats = None

    def _add_chunk(self, text, investigation, source_id, page, section):
        chunk = {"id": f"S{len(self.chunks) + 1}", "text": text, "investigation": investigation,
                 "source_id": source_id, "page": page, "section": section,
                 "terms": Counter(words(text))}
        self.chunks.append(chunk)
        self._stats = None
        return chunk["id"]

    def add_document(self, text, source_id, investigation=None, page=None, section=None):
        """Chunk one page (or any text) by section and paragraph. Returns the new chunk ids."""
        return [self._add_chunk(chunk, investigation, source_id, page, heading)
                for heading, paragraphs in split_sections(text, section)
                for chunk in pack(paragraphs)]

    def add_file(self, path, investigation=None):
        """Every page of one file, with the file name as source_id."""
        path = Path(path)
        ids, section = [], None
        for page, text in read_pages(path):
            ids += self.add_document(text, path.name, investigation, page, section)
            found = split_sections(text, section)
            section = found[-1][0] if found else section
        return ids

    def index_corpus(self, corpus):
        """One chunk per finding from evidence.load(), keeping its page or table."""
        ids = []
        for inv in corpus["investigations"]:
            for finding in inv["findings"]:
                ids.append(self._add_chunk(finding["text"], inv["acronym"], finding["source_id"],
                                           finding["page_or_table"], f"finding ({finding['type']})"))
        return ids

    def _build(self):
        df = Counter(term for chunk in self.chunks for term in chunk["terms"])
        n = len(self.chunks)
        self._stats = {
            "bm25_idf": {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()},
            "tfidf_idf": {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()},
            "avg_len": sum(sum(c["terms"].values()) for c in self.chunks) / n,
        }
        idf = self._stats["tfidf_idf"]
        for chunk in self.chunks:
            chunk["vector"] = {t: count * idf[t] for t, count in chunk["terms"].items()}
            chunk["norm"] = math.sqrt(sum(v * v for v in chunk["vector"].values()))

    def _bm25(self, query_terms, chunk):
        length = sum(chunk["terms"].values())
        score = 0.0
        for term in query_terms:
            tf = chunk["terms"].get(term, 0)
            if tf:
                scale = BM25_K1 * (1 - BM25_B + BM25_B * length / self._stats["avg_len"])
                score += self._stats["bm25_idf"][term] * tf * (BM25_K1 + 1) / (tf + scale)
        return score

    def _cosine(self, query_terms, chunk):
        idf = self._stats["tfidf_idf"]
        query = {t: c * idf[t] for t, c in Counter(query_terms).items() if t in idf}
        dot = sum(v * chunk["vector"].get(t, 0.0) for t, v in query.items())
        norm = math.sqrt(sum(v * v for v in query.values()))
        return dot / (norm * chunk["norm"]) if dot else 0.0

    def search(self, query, k=TOP_K):
        """Best k chunks for the query, or [] when nothing reaches MIN_SIMILARITY ("no context")."""
        query_terms = words(query)
        if not self.chunks or not query_terms:
            return []
        if self._stats is None:
            self._build()
        scored = [(self._cosine(query_terms, c), self._bm25(query_terms, c), c) for c in self.chunks]
        scored = [s for s in scored if s[0] >= MIN_SIMILARITY]
        if not scored:
            return []
        # BM25 has no fixed top, so scale it to 0..1 against the best match before mixing.
        best_bm25 = max(bm25 for _, bm25, _ in scored) or 1.0
        hits = []
        for cosine, bm25, chunk in scored:
            score = KEYWORD_WEIGHT * bm25 / best_bm25 + (1 - KEYWORD_WEIGHT) * cosine
            hits.append(dict({key: chunk[key] for key in
                              ("id", "text", "investigation", "source_id", "page", "section")},
                             score=round(score, 4)))
        hits.sort(key=lambda hit: -hit["score"])
        return hits[:k]


def index_folder(folder, investigation=None):
    """An Index of every .txt, .md and .pdf file in a folder, in name order."""
    index = Index()
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() in (".txt", ".md", ".pdf"):
            index.add_file(path, investigation)
    return index
