"""Shared immutable memory, explicit ranking, and whole-item token packing.

These controls isolate selection from representation and acquisition in memory
experiments. They do not implement persistence or a learned retrieval algorithm.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Iterable

from .multi_level_memory import MemoryItem
from .retrieval_engine import HybridRetrievalEngine


STRATEGIES = ("prefix", "recency", "jaccard", "bm25", "hybrid", "hybrid_no_time")
WRAPPER_START = "<memory>\n"
WRAPPER_END = "\n</memory>"


def canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryRecord:
    item_id: str
    content: str
    timestamp: float
    date: str
    role: str
    session_id: str
    turn_index: int
    start: int = 0
    end: int = 0
    access_count: int = 0
    importance: float = 0.5

    def represented(self, representation: str) -> str:
        if representation == "raw":
            return self.content
        if representation == "exchange":
            return f"User: Remember this project fact: {self.content} Reply ACK.\nAssistant: ACK"
        raise ValueError(f"Unknown representation: {representation}")

    def render(self, representation: str) -> str:
        return f"[{self.item_id} | {self.date} | {self.role}]\n{self.represented(representation)}"


class PinnedTokenizer:
    """A locally pinned BPE accounting convention, not a server billing oracle."""

    def __init__(self, path: Path, expected_sha256: str | None = None):
        from tokenizers import Tokenizer
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise ValueError("Tokenizer file differs from the pinned version")
        self.tokenizer = Tokenizer.from_file(str(path))
        self.sha256 = digest

    @lru_cache(maxsize=16384)
    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def split(self, text: str, max_tokens: int) -> list[tuple[int, int, str]]:
        """Split at Unicode character boundaries without losing source text."""
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        spans = []
        start = 0
        while start < len(text):
            if self.count(text[start:]) <= max_tokens:
                stop = len(text)
            else:
                low, high = start + 1, len(text)
                while low < high:
                    middle = (low + high + 1) // 2
                    if self.count(text[start:middle]) <= max_tokens:
                        low = middle
                    else:
                        high = middle - 1
                stop = low
                # Prefer a word boundary while retaining every character.
                boundary = text.rfind(" ", start + (stop - start) // 2, stop)
                if boundary > start and self.count(text[start:boundary + 1]) <= max_tokens:
                    stop = boundary + 1
                # BPE token counts are not monotone in character-prefix length:
                # shortening a prefix can undo merges. Verify the final boundary.
                while stop > start and self.count(text[start:stop]) > max_tokens:
                    stop -= 1
            part = text[start:stop]
            if not part or self.count(part) > max_tokens:
                raise ValueError("Cannot fit a single Unicode character in the token cap")
            spans.append((start, stop, part))
            start = stop
        return spans


def lexical_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"\w+", text.casefold()) if len(token) > 1]


class FrozenMemoryIndex:
    """Index one fixed candidate bank; ranking never reads gold evidence labels."""

    def __init__(self, records: Iterable[MemoryRecord], *, representation: str = "raw"):
        self.records = tuple(records)
        if len({record.item_id for record in self.records}) != len(self.records):
            raise ValueError("Duplicate memory IDs")
        self.representation = representation
        self.content_hash = canonical_hash([asdict(record) for record in self.records])
        self.representation_hash = canonical_hash([
            [record.item_id, record.represented(representation)] for record in self.records
        ])
        self.engine = HybridRetrievalEngine()
        self.terms = [Counter(lexical_tokens(record.represented(representation))) for record in self.records]
        self.df = Counter(term for terms in self.terms for term in terms)
        self.lengths = [sum(terms.values()) for terms in self.terms]
        self.average_length = sum(self.lengths) / max(1, len(self.lengths))
        self.items = [MemoryItem(
            content=record.represented(representation), timestamp=record.timestamp,
            access_count=record.access_count, importance=record.importance,
        ) for record in self.records]
        self._ranking_cache: dict[tuple, list[dict]] = {}

    def rank(self, query: str, strategy: str, reference_time: float) -> list[dict]:
        if strategy not in STRATEGIES:
            raise ValueError(f"Unknown selector: {strategy}")
        key = (query, strategy, reference_time)
        if key in self._ranking_cache:
            return self._ranking_cache[key]
        qterms = set(lexical_tokens(query))
        n = len(self.records)
        ranked = []
        for position, (record, terms, item) in enumerate(zip(self.records, self.terms, self.items)):
            components = {}
            if strategy == "prefix":
                score = -float(position)
            elif strategy == "recency":
                score = record.timestamp
            elif strategy in ("hybrid", "hybrid_no_time", "jaccard"):
                if strategy == "jaccard":
                    score = self.engine._jaccard_similarity(query, item.content)
                else:
                    components = self.engine.score_components(query, item, reference_time=reference_time)
                    score = components["total"]
                    if strategy == "hybrid_no_time":
                        # Only remove this contribution; do not renormalize other weights.
                        # Sum the retained terms directly: subtracting a large
                        # temporal term can leave rounding residue that changes
                        # the tie order of otherwise identical lexical scores.
                        score = (components["semantic_contribution"] + components["frequency_contribution"]
                                 + components["importance_contribution"])
            else:
                score = 0.0
                for term in qterms:
                    tf = terms.get(term, 0)
                    if tf:
                        idf = math.log(1 + (n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                        normalizer = tf + 1.2 * (1 - 0.75 + 0.75 * self.lengths[position] / max(1, self.average_length))
                        score += idf * tf * 2.2 / normalizer
            ranked.append({"item_id": record.item_id, "position": position,
                           "score": score, "components": components})
        ranked.sort(key=lambda row: (-row["score"], row["position"]))
        self._ranking_cache[key] = ranked
        return ranked

    def pack(self, ranking: list[dict], tokenizer: PinnedTokenizer, budget: int) -> dict:
        """Same ordered first-fit whole-item policy in every experimental arm."""
        context = WRAPPER_START + WRAPPER_END
        if tokenizer.count(context) > budget:
            raise ValueError("Token budget cannot hold the shared memory wrapper")
        rendered = [record.render(self.representation) for record in self.records]
        sizes = [tokenizer.count(text) for text in rendered]
        selected, skipped = [], []
        parts = []
        used = tokenizer.count(context)
        for candidate in ranking:
            i = candidate["position"]
            # A newline can change the concatenated BPE count slightly. The
            # conservative shortcut only rejects clearly oversized candidates.
            if sizes[i] > budget - used + 4:
                skipped.append(candidate["item_id"])
                continue
            trial = WRAPPER_START + "\n\n".join(parts + [rendered[i]]) + WRAPPER_END
            trial_count = tokenizer.count(trial)
            if trial_count <= budget:
                parts.append(rendered[i])
                selected.append(candidate["item_id"])
                context, used = trial, trial_count
            else:
                skipped.append(candidate["item_id"])
        return {
            "context": context, "memory_tokens": used, "budget_tokens": budget,
            "selected_ids": selected, "skipped_ids": skipped,
            "candidate_hash": self.content_hash, "representation_hash": self.representation_hash,
        }
