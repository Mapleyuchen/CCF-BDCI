"""Bounded, resumable illustration agent; all paid calls and decisions are recorded."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

from paper_content.evidence import load_evidence, read_json, sha256
from . import prompts
from .schema import canonicalize_sources, compact_prompt, compile_prompt, sources, validate_image_prompt, validate_plan, validate_review


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build_context(framework):
    brief = read_json(framework / "brief.input.json")
    outline = read_json(framework / "outline.json")
    results = load_evidence(outline, framework)
    catalog = {"research_question": brief["research_question"]}
    for method in brief.get("methods", []):
        catalog["method." + method["id"]] = method
    for key, value in brief.get("method_specification", {}).items():
        if key != "assets":  # Existing illustration instructions must not dictate the new design.
            catalog["spec." + key] = value
    for index, note in enumerate(brief.get("writing_notes", [])):
        catalog[f"note.{index}"] = note
    for result in results:
        catalog["result." + result["id"]] = {key: result[key] for key in
            ("title", "model_name", "context_chars", "context_tokens", "group_labels",
             "limitations", "groups", "paired_outcomes", "comparison") if key in result}
    return {"title": brief["title"], "research_question": brief["research_question"],
            "source_catalog": catalog,
            "evidence_sha256": {item["id"]: item["sha256"] for item in outline["evidence"]}}


def _analysis(value, catalog):
    value = canonicalize_sources(value, catalog)
    if not isinstance(value, dict) or not value.get("central_tension") or not value.get("mechanisms"):
        raise ValueError("Research analysis must describe the central tension and mechanisms")
    for item in value["mechanisms"] + value.get("visual_opportunities", []):
        sources(item.get("source_ids"), catalog)
    return value


class Stages:
    def __init__(self, model, output, previous=None, max_tokens=9000):
        self.model, self.output, self.previous = model, output, previous
        self.max_tokens = max_tokens

    def call(self, name, messages):
        request_hash = digest({"messages": messages, "model": self.model.config["client"]["model_name"],
                               "request": {"enable_thinking": False, "max_tokens": self.max_tokens, "temperature": 0.2}})
        cached = self.previous / (name + ".json") if self.previous else None
        if cached and cached.is_file():
            saved = read_json(cached)
            if saved.get("request_sha256") != request_hash:
                raise ValueError("Illustration resume requires identical stage instructions and model")
            write_json(self.output / (name + ".json"), saved)
            self.model.calls.extend({**call, "reused_from_previous_run": True} for call in saved.get("calls", []))
            print("Reusing illustration stage: " + name, flush=True)
            return saved["response"]
        print("Illustration stage: " + name, flush=True)
        start = len(self.model.calls)
        original = deepcopy(self.model.config["request"])
        self.model.config["request"] = {"enable_thinking": False, "max_tokens": self.max_tokens, "temperature": 0.2}
        try:
            value = self.model.complete(messages)
        finally:
            self.model.config["request"] = original
            for call in self.model.calls[start:]:
                call["stage"] = "illustration_" + name
            write_json(self.output / "calls.json", self.model.calls)
        write_json(self.output / (name + ".json"), {"request_sha256": request_hash,
                   "response": value, "calls": self.model.calls[start:]})
        return value

    def checked(self, name, messages, validator):
        value = self.call(name, messages)
        try:
            validated = validator(value)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            repaired = self.call(name + "_schema_repair", messages + [
                {"role": "assistant", "content": json.dumps(value)},
                {"role": "user", "content": "Correct the JSON contract without changing the evidence. Error: " + str(error)}])
            validated = validator(repaired)
        write_json(self.output / (name + "_validated.json"), {"response": validated})
        return validated


def _messages(system, payload):
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def _generate_or_resume(config, output, prompt, previous):
    from generate_methodology import generate
    old_report = previous.with_suffix(".provenance.json") if previous else None
    if old_report and old_report.is_file():
        saved = read_json(old_report)
        expected = hashlib.sha256(prompt.read_text(encoding="utf-8").strip().encode()).hexdigest()
        if saved.get("prompt_sha256") != expected:
            raise ValueError("Image resume prompt hash differs; refusing to reuse an unrelated task")
        if saved.get("status") == "completed":
            if not previous.is_file() or sha256(previous) != saved.get("image_sha256"):
                raise ValueError("Cached image is missing or its hash changed")
            shutil.copy2(previous, output)
            shutil.copy2(old_report, output.with_suffix(".provenance.json"))
            return saved
        if saved.get("task_id"):
            return generate(config, output, prompt_path=prompt, resume_task=saved["task_id"])
        raise ValueError("Previous image create attempt has no task ID; check provider billing before a new run")
    return generate(config, output, prompt_path=prompt)


def run_illustrations(framework, output, model, config, *, max_figures=2, max_redraws=0,
                      resume_from=None, simplify_on_failure=False, review_mode="fast"):
    if review_mode == "reviewed":
        return _run_reviewed(framework, output, model, config, max_figures=max_figures,
            max_redraws=max_redraws, resume_from=resume_from, simplify_on_failure=simplify_on_failure)
    if review_mode != "fast" or max_redraws or simplify_on_failure:
        raise ValueError("Automatic review/redraw requires explicit review_mode='reviewed'")
    started = time.monotonic()
    framework, output = Path(framework).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(framework) or not 1 <= max_figures <= 4:
        raise ValueError("Choose a new output directory and 1-4 figures")
    previous = Path(resume_from).resolve() if resume_from else None
    context = build_context(framework)
    import yaml
    from paper_content.model import resolve_env
    settings = resolve_env(yaml.safe_load(Path(config).read_text(encoding="utf-8-sig")) or {}).get("images", {})
    identity = {"context": context, "max_figures": max_figures, "execution_mode": "fast",
                "image_settings": {k: v for k, v in settings.items() if k != "api_key"},
                "text_model": model.config["client"]["model_name"], "pipeline_version": 4}
    if previous and read_json(previous / "input.json") != identity:
        raise ValueError("Fast resume requires identical evidence, model and settings")
    output.mkdir(parents=True)
    write_json(output / "input.json", identity)
    runner = Stages(model, output, previous, max_tokens=6500)
    report = {"schema_version": 1, "status": "running", "human_review_required": True,
              "execution_mode": "fast", "model_visual_review": "not_requested",
              "input_sha256": digest(identity), "figures": []}
    try:
        # Methods suffice for conceptual diagrams. Do not repeatedly send numerical results.
        catalog = {k: v for k, v in context["source_catalog"].items()
                   if not k.startswith(("result.", "note."))}
        raw = runner.call("fast_plan", _messages(prompts.FAST, {"title": context["title"],
            "source_catalog": catalog, "max_figures": max_figures}))
        plan = validate_plan(canonicalize_sources(raw, catalog), catalog, max_figures)
        for figure in plan["figures"]:
            if not figure.get("compact_prompt"):
                figure["compact_prompt"] = compact_prompt(figure)
                figure["prompt_origin"] = "compiled_from_design"
            validate_image_prompt({"prompt": figure.get("compact_prompt")}, figure)
            if len(figure["nodes"]) > 7 or len(figure["panels"]) != 1:
                raise ValueError("Fast diagrams require one panel and at most seven nodes")
            # Acyclic topology avoids repeated failure of long feedback arrows.
            graph = {node["id"]: [] for node in figure["nodes"]}
            for edge in figure["edges"]: graph[edge["from"]].append(edge["to"])
            def visit(node, active):
                if node in active:
                    raise ValueError("Fast diagrams cannot contain feedback loops")
                for child in graph[node]: visit(child, active | {node})
            for node in graph: visit(node, set())
            (output / (figure["id"] + ".txt")).write_text(figure["compact_prompt"].strip() + "\n", encoding="utf-8")
        write_json(output / "plan.json", plan)
        report["planning_seconds"] = round(time.monotonic() - started, 3)
        image_started = time.monotonic()
        def generate_one(figure):
            fid = figure["id"]
            target, prompt_file = output / (fid + ".png"), output / (fid + ".txt")
            _generate_or_resume(config, target, prompt_file, previous / target.name if previous else None)
            from PIL import Image
            with Image.open(target) as decoded:
                decoded.verify()
            check_file = output / (fid + "_checks.json")
            write_json(check_file, {"png_decodes": True, "source_and_graph_valid": True,
                "model_visual_review": "not_requested", "human_review_required": True})
            return {**figure, "image": target.name, "image_sha256": sha256(target),
                "prompt": prompt_file.name, "prompt_sha256": sha256(prompt_file),
                "provenance": target.with_suffix(".provenance.json").name,
                "provenance_sha256": sha256(target.with_suffix(".provenance.json")),
                "code_checks": check_file.name, "code_checks_sha256": sha256(check_file),
                "visual_review_approved": None, "image_attempts": 1}
        # Independent image jobs execute concurrently; each is submitted exactly once.
        with ThreadPoolExecutor(max_workers=min(4, len(plan["figures"]))) as pool:
            pending = [pool.submit(generate_one, figure) for figure in plan["figures"]]
            for future in pending:
                report["figures"].append(future.result())
                write_json(output / "manifest.json", report)
        report["image_wall_seconds"] = round(time.monotonic() - image_started, 3)
        report["status"] = "generated_unreviewed"
        return output / "manifest.json"
    except Exception:
        report["status"] = "failed"
        raise
    finally:
        report["calls"] = model.calls
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["new_text_calls"] = sum(not c.get("reused_from_previous_run") for c in model.calls)
        report["new_text_tokens"] = sum((c.get("usage") or {}).get("total_tokens") or 0 for c in model.calls if not c.get("reused_from_previous_run"))
        write_json(output / "manifest.json", report)


def _run_reviewed(framework, output, model, config, *, max_figures=2, max_redraws=0, resume_from=None, simplify_on_failure=False):
    framework, output = Path(framework).resolve(), Path(output).resolve()
    if output.exists() or output.is_relative_to(framework):
        raise ValueError("Choose a new illustration output directory outside the framework")
    if not 1 <= max_figures <= 4 or not 0 <= max_redraws <= 2:
        raise ValueError("Use 1-4 figures and 0-2 redraws per figure")
    previous = Path(resume_from).resolve() if resume_from else None
    context = build_context(framework)
    # Persist no API keys. Model/region/size settings form part of resume identity.
    import yaml
    from paper_content.model import resolve_env
    settings = resolve_env(yaml.safe_load(Path(config).read_text(encoding="utf-8-sig")) or {}).get("images", {})
    identity = {"context": context, "max_figures": max_figures, "max_redraws": max_redraws,
                "max_simplifications": int(simplify_on_failure),
                "image_settings": {k: v for k, v in settings.items() if k != "api_key"},
                "text_model": model.config["client"]["model_name"], "pipeline_version": 3}
    if previous:
        prior_identity = read_json(previous / "input.json")
        prior_bound = prior_identity.get("max_redraws", 0)
        prior_simplifications = prior_identity.get("max_simplifications", 0)
        # An explicit larger retry budget may continue rejected images. Completed tasks
        # and reviews remain reusable; no other input or setting is allowed to drift.
        prior_identity["max_redraws"] = max_redraws
        prior_identity["max_simplifications"] = int(simplify_on_failure)
        if prior_identity != identity or max_redraws < prior_bound or int(simplify_on_failure) < prior_simplifications:
            raise ValueError("Illustration resume requires identical evidence, settings and model (redraw bound may only increase)")
    output.mkdir(parents=True)
    write_json(output / "input.json", identity)
    runner = Stages(model, output, previous)
    report = {"schema_version": 1, "status": "running", "human_review_required": True,
              "input_sha256": digest(identity), "figures": []}
    try:
        analysis = runner.checked("research_analysis", _messages(prompts.ANALYZE, context),
                                  lambda v: _analysis(v, context["source_catalog"]))
        design_input = {**context, "analysis": analysis, "max_figures": max_figures}
        validate = lambda v: validate_plan(canonicalize_sources(v, context["source_catalog"]), context["source_catalog"], max_figures)
        plan = runner.checked("figure_design", _messages(prompts.DESIGN, design_input), validate)
        for revision in range(2):
            review = runner.checked(f"design_review_{revision}", _messages(prompts.REVIEW,
                {"source_catalog": context["source_catalog"], "plan": plan}), validate_review)
            if review["approved"]:
                break
            if revision == 1:
                raise ValueError("Diagram design still has major issues after revision; inspect saved review")
            plan = runner.checked("figure_design_revision", _messages(prompts.DESIGN,
                {**design_input, "previous_plan": plan, "required_fixes": review}), validate)
        write_json(output / "plan.json", plan)
        for figure in plan["figures"]:
            fid = figure["id"]
            (output / (fid + "_design_instructions.txt")).write_text(compile_prompt(figure), encoding="utf-8")
            art = runner.checked(fid + "_image_prompt", _messages(prompts.ARTIST, {"figure": figure}),
                                 lambda v: validate_image_prompt(v, figure))
            prompt = art["prompt"] + "\n"
            figure_sources = {k: context["source_catalog"][k] for k in figure["source_ids"]}
            for attempt in range(max_redraws + 1):
                stem = f"{fid}_v{attempt + 1}"
                prompt_file = output / (stem + ".txt")
                prompt_file.write_text(prompt, encoding="utf-8")
                target = output / (stem + ".png")
                _generate_or_resume(config, target, prompt_file, previous / target.name if previous else None)
                encoded = base64.b64encode(target.read_bytes()).decode("ascii")
                review = runner.checked(stem + "_visual_review", [
                    {"role": "system", "content": prompts.VISION},
                    {"role": "user", "content": [
                        {"type": "text", "text": json.dumps({"contract": figure, "sources": figure_sources})},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}]}], validate_review)
                if review["approved"]:
                    break
                if attempt == max_redraws:
                    if not simplify_on_failure:
                        raise ValueError(f"Figure {fid} still has major visual defects; saved all attempts for review")
                    # Repeated geometry failures need a simpler scientific representation,
                    # not more paraphrases of the same crowded graph. One replan only.
                    def simplified_contract(value):
                        value = validate_plan(canonicalize_sources(value, context["source_catalog"]), context["source_catalog"], 1)
                        item = value["figures"][0]
                        if item["id"] != fid or len(item["nodes"]) > 7:
                            raise ValueError("Simplification must retain the figure ID and use at most seven nodes")
                        graph = {node["id"]: [] for node in item["nodes"]}
                        for edge in item["edges"]:
                            graph[edge["from"]].append(edge["to"])
                        def visit(node, active):
                            if node in active:
                                raise ValueError("Simplification must be acyclic; describe repeated iteration in the caption")
                            for child in graph[node]: visit(child, active | {node})
                        for node in graph: visit(node, set())
                        return value
                    revised = runner.checked(fid + "_simplified_design", _messages(prompts.DESIGN +
                        "\nThe prior graph repeatedly failed image rendering. REDESIGN exactly this one figure, retaining its ID. "
                        "Use at most seven nodes and an ACYCLIC graph. Replace feedback loops with a clear decision branch "
                        "for a single item's fate; explain iteration in the caption. Combine adjacent operations where order "
                        "stays explicit. Put individual scoring weights in the caption rather than separate satellite nodes. "
                        "Avoid multiple arrows converging from dispersed icons. Favor a two-panel explanation with sparse "
                        "connections. Preserve all scientific meaning and source support, but change the visual representation.",
                        {"source_catalog": context["source_catalog"], "original_figure": figure,
                         "actual_rendering_failures": review, "max_figures": 1}), simplified_contract)
                    design_review = runner.checked(fid + "_simplified_design_review", _messages(prompts.REVIEW,
                        {"source_catalog": context["source_catalog"], "plan": revised}), validate_review)
                    if not design_review["approved"]:
                        raise ValueError("Simplified diagram contract failed independent design review")
                    figure = revised["figures"][0]
                    art = runner.checked(fid + "_simplified_image_prompt", _messages(prompts.ARTIST, {"figure": figure}),
                                         lambda v: validate_image_prompt(v, figure))
                    stem = fid + "_simplified_v1"
                    prompt_file = output / (stem + ".txt")
                    prompt_file.write_text(art["prompt"] + "\n", encoding="utf-8")
                    target = output / (stem + ".png")
                    _generate_or_resume(config, target, prompt_file, previous / target.name if previous else None)
                    encoded = base64.b64encode(target.read_bytes()).decode("ascii")
                    review = runner.checked(stem + "_visual_review", [
                        {"role": "system", "content": prompts.VISION},
                        {"role": "user", "content": [
                            {"type": "text", "text": json.dumps({"contract": figure,
                                "sources": {k: context["source_catalog"][k] for k in figure["source_ids"]}})},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}]}], validate_review)
                    if not review["approved"]:
                        raise ValueError("Simplified diagram still has major visual defects; inspect saved attempts")
                    attempt += 1
                    break
                correction = runner.checked(stem + "_prompt_revision", _messages(
                    prompts.ARTIST + "\nFix the listed ACTUAL visual defects. Remove ambiguous directions and any invitation to invent body text. Simplify placement while preserving the exact graph.",
                    {"contract": figure, "original_prompt": prompt, "visual_review": review}),
                    lambda v: validate_image_prompt(v, figure))
                prompt = correction["prompt"] + "\n"
            report["figures"].append({**figure, "image": target.name, "image_sha256": sha256(target),
                "prompt": prompt_file.name, "prompt_sha256": sha256(prompt_file),
                "provenance": target.with_suffix(".provenance.json").name,
                "provenance_sha256": sha256(target.with_suffix(".provenance.json")),
                "review": stem + "_visual_review_validated.json", "review_sha256": sha256(output / (stem + "_visual_review_validated.json")),
                "visual_review_approved": True, "image_attempts": attempt + 1})
            write_json(output / "manifest.json", report)
        report["status"] = "reviewed_automatically"
        write_json(output / "final_plan.json", {"figures": report["figures"]})
        return output / "manifest.json"
    except Exception:
        report["status"] = "failed"
        raise
    finally:
        report["calls"] = model.calls
        write_json(output / "manifest.json", report)


def load_bundle(manifest):
    """Offline consumers verify the exact images, prompts and reviews before rendering."""
    manifest = Path(manifest).resolve()
    bundle = read_json(manifest)
    if bundle.get("status") not in {"reviewed_automatically", "generated_unreviewed"} or not bundle.get("figures"):
        raise ValueError("Illustration bundle is incomplete or failed")
    identity = read_json(manifest.parent / "input.json")
    if digest(identity) != bundle.get("input_sha256"):
        raise ValueError("Illustration input hash mismatch")
    fast = bundle["status"] == "generated_unreviewed"
    if fast and (identity.get("execution_mode") != "fast" or bundle.get("model_visual_review") != "not_requested"):
        raise ValueError("Unreviewed images require an explicitly recorded fast execution mode")
    validate_plan(bundle, identity["context"]["source_catalog"], identity["max_figures"])
    for figure in bundle["figures"]:
        if not fast and figure.get("visual_review_approved") is not True:
            raise ValueError("Illustration has not passed automated visual review")
        if fast and figure.get("visual_review_approved") is not None:
            raise ValueError("Fast images must not claim a visual review")
        for key in ("image", "prompt", "provenance", "code_checks" if fast else "review"):
            path = (manifest.parent / figure[key]).resolve()
            if not path.is_relative_to(manifest.parent) or not path.is_file() or sha256(path) != figure[key + "_sha256"]:
                raise ValueError("Illustration file missing, outside bundle or hash mismatch: " + key)
        if not fast:
            review = validate_review(read_json(manifest.parent / figure["review"])["response"])
            if not review["approved"]:
                raise ValueError("Illustration review rejects this figure")
        image = manifest.parent / figure["image"]
        if not image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Illustration must be PNG")
        provenance = read_json(manifest.parent / figure["provenance"])
        prompt = (manifest.parent / figure["prompt"]).read_text(encoding="utf-8").strip()
        if provenance.get("image_sha256") != sha256(image) or provenance.get("prompt_sha256") != hashlib.sha256(prompt.encode()).hexdigest():
            raise ValueError("Image API provenance does not match the selected image/prompt")
    return bundle


def copy_bundle(manifest, destination):
    """Keep every attempt and decision for a self-contained manuscript handoff."""
    manifest = Path(manifest).resolve()
    bundle = load_bundle(manifest)
    if destination.exists():
        raise ValueError("Illustration destination already exists")
    shutil.copytree(manifest.parent, destination)
    return bundle
