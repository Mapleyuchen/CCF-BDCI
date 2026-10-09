"""Validate diagram contracts and render exact, content-specific image prompts."""
from __future__ import annotations

import re
from copy import deepcopy

IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")


def text(value, field, limit=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty text under {limit} characters")
    if any(ord(c) > 127 for c in value) or "\\" in value or "[[" in value:
        raise ValueError(f"{field} must be plain ASCII English without LaTeX or tokens")
    return value


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Diagram IDs must be short lowercase identifiers")
    return value


def sources(value, catalog):
    if not isinstance(value, list) or not value or any(s not in catalog for s in value):
        raise ValueError("Diagram source_ids must reference the supplied source catalog")


def canonicalize_sources(value, catalog):
    """Resolve exact method-ID aliases, never guesses; preserve the raw model output separately."""
    aliases = {}
    for key, entry in catalog.items():
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            aliases.setdefault(entry["id"], []).append(key)
    value = deepcopy(value)
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "source_ids" and isinstance(child, list):
                    item[key] = [aliases[s][0] if isinstance(s, str) and s not in catalog and len(aliases.get(s, [])) == 1 else s for s in child]
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    # The figure's source set is the explicit union of its supported nodes and metadata.
    # Validate every node source first; an unknown source still fails, never disappears.
    if isinstance(value, dict) and isinstance(value.get("figures"), list):
        for figure in value["figures"]:
            if not isinstance(figure, dict) or not isinstance(figure.get("source_ids"), list):
                continue
            if figure.get("section") == "experimental_setup":
                figure["section"] = "experiments"
            sources(figure["source_ids"], catalog)
            refs = list(figure["source_ids"])
            for node in figure.get("nodes", []):
                sources(node.get("source_ids"), catalog)
                refs.extend(node["source_ids"])
            figure["source_ids"] = list(dict.fromkeys(refs))
    return value


def validate_plan(plan, catalog, max_figures):
    if not isinstance(plan, dict) or not isinstance(plan.get("figures"), list):
        raise ValueError("Illustration plan requires a figures array")
    if not 1 <= len(plan["figures"]) <= max_figures:
        raise ValueError("Illustration count exceeds the requested bound")
    ids = set()
    for figure in plan["figures"]:
        fid = identifier(figure.get("id"))
        if fid in ids:
            raise ValueError("Duplicate figure ID")
        ids.add(fid)
        if figure.get("kind") != "conceptual_schematic" or figure.get("section") not in {"method", "experiments", "discussion"}:
            raise ValueError("Image API figures must be conceptual schematics in supported sections")
        for field in ("title", "purpose", "takeaway", "layout", "caption", "explanation"):
            text(figure.get(field), field)
        sources(figure.get("source_ids"), catalog)
        panels = figure.get("panels")
        if not isinstance(panels, list) or not 1 <= len(panels) <= 4:
            raise ValueError("A diagram needs one to four panels")
        panel_ids = set()
        for panel in panels:
            pid = identifier(panel.get("id"))
            if pid in panel_ids:
                raise ValueError("Duplicate panel ID")
            panel_ids.add(pid)
            text(panel.get("title"), "panel title", 80)
            text(panel.get("description"), "panel description")
        nodes = figure.get("nodes")
        if not isinstance(nodes, list) or not 2 <= len(nodes) <= 14:
            raise ValueError("Use two to fourteen nodes for readable publication figures")
        node_ids = set()
        for node in nodes:
            nid = identifier(node.get("id"))
            if nid in node_ids or node.get("panel") not in panel_ids:
                raise ValueError("Duplicate node or unknown panel")
            node_ids.add(nid)
            text(node.get("label"), "node label", 64)
            text(node.get("visual"), "node visual")
            sources(node.get("source_ids"), catalog)
            if not set(node["source_ids"]).issubset(figure["source_ids"]):
                raise ValueError("Figure source_ids must include its node sources")
        edges = figure.get("edges")
        if not isinstance(edges, list) or len(edges) > 24:
            raise ValueError("Edges must be a bounded array")
        for edge in edges:
            if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
                raise ValueError("Diagram edge refers to an unknown node")
            if edge["from"] == edge["to"]:
                raise ValueError("Self edges are not supported")
            if edge.get("label"):
                text(edge["label"], "edge label", 64)
        if not isinstance(figure.get("avoid"), list) or not figure["avoid"]:
            raise ValueError("Each diagram must state content-specific exclusions")
        for item in figure["avoid"]:
            text(item, "avoid")
    return plan


def validate_review(review):
    if not isinstance(review, dict) or type(review.get("approved")) is not bool or not isinstance(review.get("issues"), list):
        raise ValueError("Review must contain a boolean approved and an issues array")
    for issue in review["issues"]:
        if not isinstance(issue, dict) or issue.get("severity") not in {"major", "minor"}:
            raise ValueError("Review issues require major/minor severity")
        text(issue.get("issue"), "review issue")
        text(issue.get("fix"), "review fix")
    if review["approved"] and any(i["severity"] == "major" for i in review["issues"]):
        raise ValueError("A diagram with major issues cannot be approved")
    return review


def validate_image_prompt(value, figure):
    prompt = text(value.get("prompt"), "image prompt", 6000)
    if len(prompt.split()) > 650:
        raise ValueError("Image prompt must stay under 650 words; keep research discussion outside the image prompt")
    missing = [n["label"] for n in figure["nodes"] if n["label"] not in prompt]
    if missing:
        raise ValueError("Image prompt omits exact node labels: " + ", ".join(missing))
    return value


def compact_prompt(figure):
    """Render the existing design without another model call when prose is omitted."""
    labels = {node["id"]: node["label"] for node in figure["nodes"]}
    lines = ["Scientific schematic, landscape 7:4, white, navy/teal/amber. Large sans-serif labels.",
             "Layout: " + figure["layout"],
             "Meaningful scientific glyphs; interiors use geometric strokes, never body text."]
    for node in figure["nodes"]:
        lines.append('"' + node["label"] + '": ' + node["visual"])
    lines.append("Draw exactly these directed arrows; no extra connections; arrow labels omitted:")
    for edge in figure["edges"]:
        lines.append('"' + labels[edge["from"]] + '" -> "' + labels[edge["to"]] + '".')
    lines += ["Keep parallel lanes separate; arrows end at the named glyph. No numerical results, equations or small prose.",
              "Exact text whitelist (print each once): " + "; ".join('"' + n["label"] + '"' for n in figure["nodes"])]
    return "\n".join(lines)


def compile_prompt(figure):
    lines = [
        "Use case: scientific-educational / infographic-diagram.",
        "Asset: a publication-quality English research paper schematic, landscape 7:4.",
        "Communication goal: " + figure["purpose"],
        "Reader takeaway: " + figure["takeaway"],
        "Composition and visual hierarchy: " + figure["layout"],
        "White background, generous margins, large legible sans-serif labels, flat editorial scientific illustration.",
        "Use a consistent navy / teal palette and restrained amber for cost or constraints. Color is semantic.",
        "Use meaningful miniature documents, memory cards, containers or operations when specified below; avoid a wall of text boxes.",
        'Overall title (verbatim): "' + figure["title"] + '".',
        "Panel specification (IDs are instructions only; never print IDs):",
    ]
    for panel in figure["panels"]:
        lines.append(f'{panel["id"]}: title "{panel["title"]}". {panel["description"]}')
    lines.append("Exact node labels and their visual treatments:")
    labels = {node["id"]: node["label"] for node in figure["nodes"]}
    for node in figure["nodes"]:
        lines.append(f'{node["id"]} in {node["panel"]}: label "{node["label"]}". {node["visual"]}')
    lines.append("Directed connections; draw only these arrows, with clean unambiguous endpoints:")
    for edge in figure["edges"]:
        label = f'; arrow label "{edge["label"]}"' if edge.get("label") else "; no arrow text"
        lines.append(f'"{labels[edge["from"]]}" -> "{labels[edge["to"]]}"{label}.')
    lines += [
        "Draw explanatory relationships, never measured charts, performance bars, invented numbers or equations.",
        "Render only the title, panel titles, node labels and specified arrow labels as text. Do not print planning notes or the caption.",
        "No tiny text, crossing arrows, ambiguous branches, decorative badges, logos, gradients, 3D, watermark or repeated labels.",
        "Content-specific exclusions: " + "; ".join(figure["avoid"]),
    ]
    return "\n\n".join(lines) + "\n"
