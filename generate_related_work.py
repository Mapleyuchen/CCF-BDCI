#!/usr/bin/env python3
"""
generate_related_work.py
Autonomous Related Work generator for paper:
  "Multi-Level Memory Architecture for Intelligent Agents: A Hybrid Retrieval Approach"

Usage:
    python generate_related_work.py

Outputs:
    related_work_section.tex   -- drop-in \section{Related Work} LaTeX
    related_work_refs.bib      -- BibTeX entries for all cited papers
    related_work_papers.json   -- raw search results (for auditing)
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bootstrap: add TJU-CIP2026-Final/src to path and load its .env
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
TJU_ROOT = PROJECT_ROOT / "TJU-CIP2026-Final"
sys.path.insert(0, str(TJU_ROOT))

from dotenv import load_dotenv
load_dotenv(TJU_ROOT / ".env")

from src.services.paper_search import ArxivSearcher, SemanticScholarSearcher
from src.core.config import Settings
from src.core.llm import LLMClient
from src.core.models import PaperItem

# ---------------------------------------------------------------------------
# Search queries targeting the paper's three core themes
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "agent memory system hierarchical LLM large language model",
    "multi-level memory working memory episodic memory intelligent agent",
    "hybrid retrieval semantic similarity temporal decay frequency ranking",
    "multi-agent collaboration memory sharing synchronization",
    "retrieval augmented generation knowledge base long-term memory agent",
]

MAX_PER_QUERY = 8   # arXiv + S2 each
TOTAL_TARGET  = 30  # after dedup, aim for this many


# ---------------------------------------------------------------------------
# Cite-key generation
# ---------------------------------------------------------------------------

def _ascii_slug(text: str) -> str:
    """Transliterate unicode to ASCII and keep only word chars."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_bytes = nfkd.encode("ascii", "ignore")
    return re.sub(r"[^a-zA-Z0-9]", "", ascii_bytes.decode("ascii"))


def make_citekey(paper: PaperItem, seen: Dict[str, int]) -> str:
    """authorYYYYkeyword, disambiguated with a suffix if needed."""
    first_author = (paper.authors[0] if paper.authors else "unknown").split()[-1]
    first_author = _ascii_slug(first_author).lower()[:12]
    year = (paper.published or "2024")[:4]
    # first meaningful word from title (skip stop words)
    stop = {"a", "an", "the", "of", "in", "on", "for", "and", "with",
            "to", "is", "are", "via", "by", "as", "at", "from"}
    title_words = [w for w in re.split(r"\W+", paper.title.lower()) if w and w not in stop]
    keyword = _ascii_slug(title_words[0])[:10] if title_words else "paper"
    base = f"{first_author}{year}{keyword}"
    if base not in seen:
        seen[base] = 0
        return base
    seen[base] += 1
    return f"{base}{chr(ord('a') + seen[base] - 1)}"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(papers: List[PaperItem]) -> List[PaperItem]:
    seen_ids: set = set()
    seen_titles: set = set()
    out: List[PaperItem] = []
    for p in papers:
        tid = re.sub(r"\W+", "", p.title.lower())
        pid = p.paper_id or ""
        if pid and pid in seen_ids:
            continue
        if tid in seen_titles:
            continue
        if pid:
            seen_ids.add(pid)
        seen_titles.add(tid)
        out.append(p)
    return out


# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

RELATED_WORK_SYSTEM = (
    "You are an expert academic writer producing LaTeX content for an ICLR-format paper. "
    "Write in formal English. Use only the cite keys provided -- do NOT invent new ones. "
    "Every claim that refers to a paper MUST use \\citep{citekey}. "
    "Do not add \\section{Related Work} -- only the subsections and paragraphs. "
    "Do not use any package macros not in the preamble. "
    "Output only valid LaTeX; no markdown, no commentary outside LaTeX comments."
)

RELATED_WORK_USER_TMPL = """\
The paper is titled:
  "Multi-Level Memory Architecture for Intelligent Agents: A Hybrid Retrieval Approach"

It proposes:
1. A three-layer agent memory (working / task / project) with per-layer TTL and capacity.
2. A hybrid retrieval score combining semantic similarity, temporal decay, access frequency,
   and an importance weight.
3. A team memory synchronization protocol for multi-agent settings.
4. Implementation and evaluation in JiuwenSwarm.

Below is a JSON list of papers discovered from arXiv and Semantic Scholar.
Each entry has: citekey, title, authors (first 3), year, abstract_snippet.

{papers_json}

Write a \\section{{Related Work}} body (no \\section header, only \\subsection).
Use exactly four subsections in this order:
  \\subsection{{Agent Memory Systems}}
  \\subsection{{Retrieval Methods for Agent Memory}}
  \\subsection{{Multi-Agent Collaboration}}
  \\subsection{{LLM-Based Autonomous Agents}}

Rules:
- Each subsection: 3-5 sentences, 2-4 citations from the list above.
- Cite using \\citep{{citekey}}.
- Do not cite papers not in the provided list.
- After the four subsections, write one short paragraph (no subsection header) that
  positions our work relative to the surveyed literature.
- Output only the LaTeX text; no markdown fences, no explanations.
"""

BIBTEX_SYSTEM = (
    "You produce BibTeX entries. "
    "For each paper described, output one @article or @inproceedings entry. "
    "Use the exact cite key given. "
    "Fill as many fields as the data supports. "
    "Output ONLY the BibTeX blocks, one after another, no commentary."
)

BIBTEX_USER_TMPL = """\
Produce BibTeX entries for the following papers.
Use the exact cite key shown in each entry.

{papers_json}

Output format: one complete BibTeX entry per paper, back to back.
"""


# ---------------------------------------------------------------------------
# Search & collect
# ---------------------------------------------------------------------------

def collect_papers() -> List[PaperItem]:
    arxiv_searcher = ArxivSearcher(max_results=MAX_PER_QUERY)
    s2_searcher    = SemanticScholarSearcher()
    all_papers: List[PaperItem] = []

    for i, q in enumerate(SEARCH_QUERIES, 1):
        print(f"[{i}/{len(SEARCH_QUERIES)}] arXiv: {q[:60]}")
        try:
            results = arxiv_searcher.search(q, max_results=MAX_PER_QUERY)
            all_papers.extend(results)
        except Exception as exc:
            print(f"  arXiv failed: {exc}")
        time.sleep(2)  # respect rate limits

        print(f"[{i}/{len(SEARCH_QUERIES)}] S2:    {q[:60]}")
        try:
            results = s2_searcher.search(q, max_results=MAX_PER_QUERY)
            all_papers.extend(results)
        except Exception as exc:
            print(f"  S2 failed: {exc}")
        time.sleep(1)

    deduped = deduplicate(all_papers)
    print(f"\nCollected {len(all_papers)} raw, {len(deduped)} after dedup.")
    return deduped[:TOTAL_TARGET]


# ---------------------------------------------------------------------------
# Build paper metadata list with citekeys
# ---------------------------------------------------------------------------

def build_paper_list(papers: List[PaperItem]) -> List[dict]:
    seen: Dict[str, int] = {}
    records = []
    for p in papers:
        key = make_citekey(p, seen)
        records.append({
            "citekey":          key,
            "title":            p.title,
            "authors":          p.authors[:3],
            "year":             (p.published or "")[:4] or "2024",
            "abstract_snippet": (p.abstract or "")[:280].replace("\n", " "),
            "url":              p.url,
            "categories":       p.categories[:3],
        })
    return records


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def generate_related_work_latex(llm: LLMClient, paper_records: List[dict]) -> str:
    papers_json = json.dumps(paper_records, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": RELATED_WORK_SYSTEM},
        {"role": "user",   "content": RELATED_WORK_USER_TMPL.format(papers_json=papers_json)},
    ]
    print("\nCalling LLM to generate Related Work LaTeX...")
    return llm.invoke(messages, temperature=0.3)


def generate_bibtex(llm: LLMClient, paper_records: List[dict]) -> str:
    papers_json = json.dumps(paper_records, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": BIBTEX_SYSTEM},
        {"role": "user",   "content": BIBTEX_USER_TMPL.format(papers_json=papers_json)},
    ]
    print("Calling LLM to generate BibTeX entries...")
    return llm.invoke(messages, temperature=0.1)


# ---------------------------------------------------------------------------
# Post-process LaTeX: ensure \section{Related Work} wrapper
# ---------------------------------------------------------------------------

SECTION_HEADER = r"\section{Related Work}"

def wrap_section(latex: str) -> str:
    """Add \section{Related Work} if the LLM omitted it."""
    stripped = latex.strip()
    if not stripped.startswith(SECTION_HEADER):
        return SECTION_HEADER + "\n\n" + stripped
    return stripped


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_outputs(
    out_dir:       Path,
    latex:         str,
    bibtex:        str,
    paper_records: List[dict],
) -> Tuple[Path, Path, Path]:

    tex_path  = out_dir / "related_work_section.tex"
    bib_path  = out_dir / "related_work_refs.bib"
    json_path = out_dir / "related_work_papers.json"

    tex_path.write_text(latex,   encoding="utf-8")
    bib_path.write_text(bibtex,  encoding="utf-8")
    json_path.write_text(
        json.dumps(paper_records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Also append new BibTeX entries to the master .bib, avoiding duplicates
    master_bib = out_dir / "iclr2027_conference.bib"
    if master_bib.exists():
        existing = master_bib.read_text(encoding="utf-8")
        # collect keys already in master
        existing_keys = set(re.findall(r"@\w+\{(\S+?),", existing))
        new_entries: List[str] = []
        for block in re.split(r"\n(?=@)", bibtex.strip()):
            block = block.strip()
            if not block:
                continue
            m = re.match(r"@\w+\{(\S+?),", block)
            if m and m.group(1) not in existing_keys:
                new_entries.append(block)
        if new_entries:
            with master_bib.open("a", encoding="utf-8") as f:
                f.write("\n\n" + "\n\n".join(new_entries))
            print(f"Appended {len(new_entries)} new entries to {master_bib.name}")
        else:
            print("No new entries to add to master .bib (all already present).")

    return tex_path, bib_path, json_path


# ---------------------------------------------------------------------------
# Compilation check
# ---------------------------------------------------------------------------

COMPILE_WRAPPER = r"""\documentclass{{article}}
\usepackage{{iclr2027_conference,times}}
\usepackage{{hyperref}}
\usepackage{{url}}
\usepackage{{natbib}}
\begin{{document}}
{body}
\bibliography{{iclr2027_conference,related_work_refs}}
\bibliographystyle{{iclr2027_conference}}
\end{{document}}
"""

def try_compile(out_dir: Path, tex_body: str) -> bool:
    """Attempt a pdflatex compilation in out_dir; return True if successful."""
    import subprocess, shutil
    if not shutil.which("pdflatex"):
        print("pdflatex not found on PATH; skipping compilation check.")
        return False

    test_tex = out_dir / "_rw_test.tex"
    test_tex.write_text(
        COMPILE_WRAPPER.format(body=tex_body),
        encoding="utf-8",
    )
    for pass_num in range(2):
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "_rw_test.tex"],
            cwd=str(out_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and pass_num == 1:
            print("pdflatex pass 2 failed. Check _rw_test.log for details.")
            return False

    # bibtex pass
    subprocess.run(
        ["bibtex", "_rw_test"],
        cwd=str(out_dir),
        capture_output=True,
    )
    # final pdflatex pass
    subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "_rw_test.tex"],
        cwd=str(out_dir),
        capture_output=True,
    )

    pdf = out_dir / "_rw_test.pdf"
    if pdf.exists():
        print(f"Compilation OK -> {pdf}")
        return True
    return False


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Related Work Generator ===")
    print(f"Paper: Multi-Level Memory Architecture for Intelligent Agents\n")

    out_dir = PROJECT_ROOT
    settings = Settings.from_env(TJU_ROOT)
    llm = LLMClient(settings)

    if not llm.available:
        print("ERROR: LLM_API_KEY is not set in TJU-CIP2026-Final/.env")
        print("Set it and re-run. Exiting.")
        sys.exit(1)

    # --- Step 1: search ---
    print("Step 1: Searching papers on arXiv and Semantic Scholar...")
    papers = collect_papers()

    # --- Step 2: assign citekeys ---
    paper_records = build_paper_list(papers)
    print(f"Step 2: Assigned {len(paper_records)} cite keys.")

    # --- Step 3: generate LaTeX ---
    latex_raw = generate_related_work_latex(llm, paper_records)
    latex     = wrap_section(latex_raw)

    # --- Step 4: generate BibTeX ---
    bibtex = generate_bibtex(llm, paper_records)

    # --- Step 5: write files ---
    print("Step 5: Writing output files...")
    tex_path, bib_path, json_path = write_outputs(out_dir, latex, bibtex, paper_records)

    print(f"\nDone.")
    print(f"  LaTeX section : {tex_path}")
    print(f"  BibTeX entries: {bib_path}")
    print(f"  Paper JSON    : {json_path}")

    # --- Step 6: try compile ---
    print("\nStep 6: Attempting local LaTeX compilation check...")
    try_compile(out_dir, latex)

    print("\nTo include in your paper, add to paper_iclr2027.tex:")
    print("  \\input{related_work_section}")
    print("  and add related_work_refs to your \\bibliography{} line.")


if __name__ == "__main__":
    main()
