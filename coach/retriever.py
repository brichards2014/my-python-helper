"""BM25 retriever over two sources: strategy notes and past-game statistics.

No third-party packages are needed. Documents come from:
  * knowledge/*.md      strategy notes, split into one document per "## " section
  * data/past_games.json aggregated results of simulated games (built by scripts/build_past_games.py)
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
PAST_GAMES_PATH = ROOT / "data" / "past_games.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "so", "the", "to", "with", "you", "your",
}

K1 = 1.5
B = 0.75


@dataclass(frozen=True)
class Document:
    doc_id: str
    source: str  # "knowledge" or "history"
    title: str
    text: str
    advice: str | None = None  # template filled in by the agent
    fields: dict = field(default_factory=dict)  # extra values the template can use


@dataclass(frozen=True)
class Hit:
    doc: Document
    score: float
    relevance: float  # score divided by the best score a perfect match could reach, 0 to 1


def tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alphanumerics, drop stopwords, strip simple plurals."""
    tokens = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOPWORDS:
            continue
        if word.endswith("sses"):
            word = word[:-2]  # guesses -> guess
        elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        tokens.append(word)
    return tokens


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


EXTRA_FIELD = re.compile(r"^(Hint\d|Lesson|Label|Pattern):\s*(.*)$")


def load_knowledge(directory: Path = KNOWLEDGE_DIR) -> list[Document]:
    """Read every markdown file and return one Document per '## ' section.

    Besides Tags and Advice, a section may carry Hint1..Hint3, Lesson, Label and Pattern lines.
    They are stored in Document.fields (keys are lowercased).
    """
    documents: list[Document] = []
    for path in sorted(Path(directory).glob("*.md")):
        file_title = path.stem
        sections: list[dict] = []
        current: dict | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                file_title = line[2:].strip()
            elif line.startswith("## "):
                current = {"title": line[3:].strip(), "tags": "", "advice": None, "body": [], "fields": {}}
                sections.append(current)
            elif current is not None:
                if line.startswith("Tags:"):
                    current["tags"] = line[len("Tags:"):].strip()
                elif line.startswith("Advice:"):
                    current["advice"] = line[len("Advice:"):].strip()
                elif EXTRA_FIELD.match(line):
                    key, value = EXTRA_FIELD.match(line).groups()
                    current["fields"][key.lower()] = value.strip()
                elif line.strip():
                    current["body"].append(line.strip())
        for section in sections:
            text = " ".join([file_title, section["title"], section["tags"], *section["body"]])
            documents.append(
                Document(
                    doc_id=f"{path.stem}#{_slug(section['title'])}",
                    source="knowledge",
                    title=section["title"],
                    text=text,
                    advice=section["advice"],
                    fields=section["fields"],
                )
            )
    return documents


def load_references(path: Path) -> list[Document]:
    """Read cited public references (title, summary, url, pattern). Empty list if the file is missing."""
    path = Path(path)
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    return [
        Document(
            doc_id=record["id"],
            source="reference",
            title=record["title"],
            text=" ".join([record["title"], record["summary"], record.get("keywords", "")]),
            fields={"url": record["url"], "pattern": record["pattern"], "title": record["title"]},
        )
        for record in records
    ]


def load_past_games(path: Path = PAST_GAMES_PATH) -> list[Document]:
    """Read aggregated past-game statistics. Returns an empty list if the file is missing."""
    path = Path(path)
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    return [
        Document(
            doc_id=record["id"],
            source="history",
            title=record["title"],
            text=record["summary"],
            advice=record.get("advice"),
            fields=record.get("fields", {}),
        )
        for record in records
    ]


class Retriever:
    """Okapi BM25 over a fixed list of documents."""

    def __init__(self, documents: list[Document]):
        self.documents = list(documents)
        self._tokens = [tokenize(d.text) for d in self.documents]
        self._lengths = [len(t) for t in self._tokens]
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        self._df: dict[str, int] = {}
        for tokens in self._tokens:
            for term in set(tokens):
                self._df[term] = self._df.get(term, 0) + 1

    @classmethod
    def default(cls) -> "Retriever":
        return cls(load_knowledge() + load_past_games())

    def _idf(self, term: str) -> float:
        n = len(self.documents)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 3, source: str | None = None) -> list[Hit]:
        terms = tokenize(query)
        if not terms or not self.documents:
            return []
        known = [t for t in set(terms) if t in self._df]
        max_possible = sum(self._idf(t) * (K1 + 1) for t in known)
        hits: list[Hit] = []
        for index, doc in enumerate(self.documents):
            if source and doc.source != source:
                continue
            counts: dict[str, int] = {}
            for token in self._tokens[index]:
                counts[token] = counts.get(token, 0) + 1
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * self._lengths[index] / self._avg_len))
                score += self._idf(term) * norm
            if score > 0:
                relevance = min(1.0, score / max_possible) if max_possible else 0.0
                hits.append(Hit(doc=doc, score=round(score, 4), relevance=round(relevance, 4)))
        hits.sort(key=lambda h: -h.score)
        return hits[:k]
