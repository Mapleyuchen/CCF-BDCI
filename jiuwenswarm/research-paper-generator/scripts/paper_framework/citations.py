"""Normalize supplied metadata without inventing or downloading references."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import unquote


def latex_text(value: str) -> str:
    """Treat metadata as text, never as executable LaTeX."""
    escapes = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
        "$": r"\$", "&": r"\&", "#": r"\#", "%": r"\%",
        "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(escapes.get(char, char) for char in " ".join(value.split()))


def required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return " ".join(value.split())


def normalize_arxiv(value: str) -> str:
    value = re.sub(r"^https?://(?:www\.)?(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", value.strip(), flags=re.I)
    value = re.sub(r"^arxiv:", "", value, flags=re.I)
    value = re.sub(r"\.pdf$", "", value)
    value = re.sub(r"v\d+$", "", value)
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z.-]+(?:\.[A-Z]{2})?/\d{7})", value):
        raise ValueError(f"Invalid arXiv ID: {value}")
    return value.lower()


def normalize_doi(value: str) -> str:
    value = unquote(re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value.strip(), flags=re.I)).lower()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", value):
        raise ValueError(f"Invalid DOI: {value}")
    return value


def _fingerprint(title: str, authors: list[str], year: str) -> str:
    value = f"{title}|{'|'.join(authors)}|{year}"
    return re.sub(r"[^\w|]", "", unicodedata.normalize("NFKC", value).casefold())


def build_citations(raw: object) -> dict:
    """Accept literature_search.py's list; reject incomplete/ambiguous metadata.

    DOI/arXiv identities and exact normalized title+authors+year deduplicate
    records. Conflicting identifiers or metadata fail rather than silently merge.
    """
    if not isinstance(raw, list):
        raise ValueError("Literature input must be a JSON array")
    entries: list[dict] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"literature[{index}] must be an object")
        title = required_text(item.get("title"), f"literature[{index}].title")
        authors = item.get("authors")
        if not isinstance(authors, list) or not authors:
            raise ValueError(f"literature[{index}].authors must be a non-empty string array")
        authors = [required_text(a, "author") for a in authors]
        year = str(item.get("year") or str(item.get("published", ""))[:4])
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError(f"literature[{index}] needs year or an ISO published date")
        arxiv = normalize_arxiv(required_text(item["arxiv_id"], "arxiv_id")) if item.get("arxiv_id") else None
        doi = normalize_doi(required_text(item["doi"], "doi")) if item.get("doi") else None
        fingerprint = _fingerprint(title, authors, year)
        identity = f"doi:{doi}" if doi else f"arxiv:{arxiv}" if arxiv else f"metadata:{fingerprint}"
        aliases = [identity]
        if arxiv:
            aliases.append(f"arxiv:{arxiv}")
        if item.get("id"):
            aliases.append(required_text(item["id"], "literature.id"))
        url = item.get("url") or (f"https://doi.org/{doi}" if doi else f"https://arxiv.org/abs/{arxiv}" if arxiv else None)
        if url is not None:
            url = required_text(url, "literature.url")
            if not re.match(r"^https?://\S+$", url):
                raise ValueError("literature.url must be an HTTP(S) URL")
        journal = item.get("journal")
        if journal is not None:
            journal = required_text(journal, "literature.journal")
        record = {
            "title": title, "authors": authors, "year": year, "arxiv_id": arxiv,
            "doi": doi, "url": url, "journal": journal, "fingerprint": fingerprint,
            "source_ids": sorted(set(aliases)), "source_indices": [index],
            "verification": "supplied_metadata_not_independently_verified",
        }
        matches = [old for old in entries if
                   (doi and doi == old["doi"]) or (arxiv and arxiv == old["arxiv_id"]) or
                   fingerprint == old["fingerprint"] or set(aliases) & set(old["source_ids"])]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous duplicate literature: {title}")
        if matches:
            old = matches[0]
            if fingerprint != old["fingerprint"] or any(
                old[field] and record[field] and old[field] != record[field]
                for field in ("doi", "arxiv_id", "journal")
            ):
                raise ValueError(f"Conflicting metadata for literature: {title}")
            for field in ("doi", "arxiv_id", "url", "journal"):
                old[field] = old[field] or record[field]
            old["source_ids"] = sorted(set(old["source_ids"] + aliases))
            old["source_indices"].append(index)
        else:
            entries.append(record)
    by_source_id = {}
    for record in entries:
        identity = (f"doi:{record['doi']}" if record["doi"] else
                    f"arxiv:{record['arxiv_id']}" if record["arxiv_id"] else
                    f"metadata:{record['fingerprint']}")
        record["id"] = identity
        # Content-based keys do not depend on input ordering or explicit user IDs.
        record["cite_key"] = "ref_" + hashlib.sha256(identity.encode()).hexdigest()[:16]
        record.pop("fingerprint")
        for alias in record["source_ids"]:
            by_source_id[alias] = record["cite_key"]
    entries.sort(key=lambda entry: entry["cite_key"])
    return {"schema_version": 1, "entries": entries, "by_source_id": by_source_id}


def bibliography(citations: dict) -> str:
    blocks = ["% Supplied metadata only; verify against primary sources before submission.\n"]
    for entry in citations["entries"]:
        fields = {
            "title": "{" + latex_text(entry["title"]) + "}",
            "author": " and ".join(latex_text(a) for a in entry["authors"]),
            "year": entry["year"],
        }
        for name in ("journal", "doi", "url"):
            if entry[name]:
                fields[name] = latex_text(entry[name])
        if entry["arxiv_id"]:
            fields["eprint"] = entry["arxiv_id"]
            fields["archivePrefix"] = "arXiv"
            fields.setdefault("howpublished", f"arXiv preprint arXiv:{entry['arxiv_id']}")
        kind = "article" if entry["journal"] else "misc"
        body = ",\n".join(f"  {key} = {{{value}}}" for key, value in fields.items())
        blocks.append(f"@{kind}{{{entry['cite_key']},\n{body}\n}}\n")
    return "\n".join(blocks)
