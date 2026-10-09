"""Diagram grounding, bounded revisions, paid-task reuse and offline manuscript handoff."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE / "scripts"))
from paper_illustration.pipeline import run_illustrations, load_bundle, build_context, write_json
from paper_illustration.schema import canonicalize_sources, validate_plan, compile_prompt, validate_review
from paper_content.prose import render_paragraph


CONTEXT = {"title": "A study", "research_question": "How is evidence used?",
           "source_catalog": {"method": "Documents are selected and then read."}, "evidence_sha256": {}}
ANALYSIS = {"central_tension": "Capacity versus information.",
            "mechanisms": [{"explanation": "Select then read.", "source_ids": ["method"]}]}
PLAN = {"figures": [{"id": "evidence_flow", "kind": "conceptual_schematic", "section": "method",
    "title": "Evidence flow", "purpose": "Explain how a reader gets evidence.", "takeaway": "Selection precedes reading.",
    "source_ids": ["method"], "layout": "Documents on the left; reading on the right.",
    "panels": [{"id": "pipeline", "title": "Pipeline", "description": "A horizontal evidence path."}],
    "nodes": [{"id": "docs", "panel": "pipeline", "label": "Documents", "visual": "A stack of cards on the left.", "source_ids": ["method"]},
              {"id": "reader", "panel": "pipeline", "label": "Read evidence", "visual": "A reading operation on the right.", "source_ids": ["method"]}],
    "edges": [{"from": "docs", "to": "reader", "label": "Selected evidence"}],
    "caption": "A conceptual schematic of evidence selection, not measured results.",
    "explanation": "The reader receives selected evidence through the illustrated path.",
    "avoid": ["Do not invent embeddings or measured results."]}]}
PASS = {"approved": True, "issues": []}
FAIL = {"approved": False, "issues": [{"severity": "major", "issue": "An arrow points backwards.", "fix": "Point the arrow from Documents to Read evidence."}]}


class Model:
    def __init__(self, replies):
        self.replies = deepcopy(replies)
        self.calls = []
        self.config = {"client": {"model_name": "fake-model"}, "request": {"max_tokens": 123}}

    def complete(self, messages):
        from paper_illustration import prompts
        if messages[0]["content"] == prompts.ARTIST:
            self.calls.append({"model": "fake-model", "usage": {"total_tokens": 10}})
            return {"prompt": compile_prompt(PLAN["figures"][0])}
        if not self.replies:
            raise AssertionError("Unexpected paid model call")
        self.calls.append({"model": "fake-model", "usage": {"total_tokens": 10}})
        return self.replies.pop(0)


def fake_image(config, output, *, prompt_path=None, **kwargs):
    from PIL import Image
    Image.new("RGB", (400, 200), "white").save(output)
    report = {"status": "completed", "image_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "prompt_sha256": hashlib.sha256(prompt_path.read_text(encoding="utf-8").strip().encode()).hexdigest()}
    write_json(output.with_suffix(".provenance.json"), report)
    return report


class IllustrationTests(unittest.TestCase):
    def settings(self, root):
        config = root / "config.yaml"
        config.write_text("images:\n  api_key: ${DASHSCOPE_API_KEY}\n  model: fake-image\n", encoding="utf-8")
        return config

    def run_agent(self, root, replies=None, previous=None, max_redraws=1, simplify=False):
        config = self.settings(root)
        output = root / ("resumed" if previous else "illustrations")
        model = Model(replies if replies is not None else [ANALYSIS, PLAN, PASS, PASS])
        with patch("paper_illustration.pipeline.build_context", return_value=CONTEXT), patch("generate_methodology.generate", side_effect=fake_image) as images:
            result = run_illustrations(root / "framework", output, model, config, resume_from=previous, max_redraws=max_redraws, simplify_on_failure=simplify, review_mode="reviewed")
        return result, images.call_count, model

    def test_reject_unknown_sources_broken_edges_and_duplicate_ids(self):
        mutations = [lambda p: p["figures"][0]["nodes"][0].update(source_ids=["invented"]),
                     lambda p: p["figures"][0]["edges"][0].update(to="missing"),
                     lambda p: p["figures"].append(deepcopy(p["figures"][0]))]
        for mutate in mutations:
            plan = deepcopy(PLAN)
            mutate(plan)
            with self.assertRaises(ValueError): validate_plan(plan, CONTEXT["source_catalog"], 2)

    def test_prompt_has_exact_labels_relationships_and_exclusions(self):
        prompt = compile_prompt(PLAN["figures"][0])
        self.assertIn('"Documents" -> "Read evidence"', prompt)
        self.assertIn("Do not invent embeddings", prompt)
        self.assertIn("not measured", PLAN["figures"][0]["caption"])

    def test_exact_source_alias_normalization_never_accepts_unknown_sources(self):
        catalog = {"method.actual": {"id": "method", "description": "Known method"}, "other": "Other supported detail"}
        plan = deepcopy(PLAN)
        plan["figures"][0]["nodes"][0]["source_ids"].append("other")
        normalized = canonicalize_sources(plan, catalog)
        self.assertEqual(normalized["figures"][0]["source_ids"], ["method.actual", "other"])
        self.assertEqual(plan["figures"][0]["source_ids"], ["method"])
        plan["figures"][0]["nodes"][0]["source_ids"].append("invented")
        with self.assertRaisesRegex(ValueError, "source_ids"):
            canonicalize_sources(plan, catalog)

    def test_resume_does_not_make_another_paid_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, count, model = self.run_agent(root)
            self.assertEqual(count, 1)
            self.assertEqual(model.config["request"], {"max_tokens": 123})
            resumed, count, model = self.run_agent(root, [], manifest.parent)
            self.assertEqual(count, 0)
            self.assertTrue(all(c["reused_from_previous_run"] for c in model.calls))
            self.assertEqual(load_bundle(resumed)["figures"][0]["image_attempts"], 1)

    def test_resume_rejects_changed_evidence_before_any_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, _, _ = self.run_agent(root)
            with patch("paper_illustration.pipeline.build_context", return_value={**CONTEXT, "title": "Changed"}):
                with self.assertRaisesRegex(ValueError, "identical evidence"):
                    run_illustrations(root / "framework", root / "changed", Model([]), self.settings(root), resume_from=manifest.parent, review_mode="reviewed")

    def test_visual_failure_drives_specific_redraw(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, count, _ = self.run_agent(Path(directory), [ANALYSIS, PLAN, PASS, FAIL,
                {"prompt": compile_prompt(PLAN["figures"][0]) + "Make the arrow unambiguously left to right."}, PASS])
            self.assertEqual(count, 2)
            bundle = load_bundle(manifest)
            self.assertEqual(bundle["figures"][0]["image_attempts"], 2)
            self.assertTrue((manifest.parent / "evidence_flow_v1.png").is_file())

    def test_explicit_larger_redraw_bound_continues_without_repaying_prior_calls(self):
        correction = {"prompt": compile_prompt(PLAN["figures"][0]) + "Keep the correct arrow direction."}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "visual defects"):
                self.run_agent(root, [ANALYSIS, PLAN, PASS, FAIL, correction, FAIL])
            manifest, count, model = self.run_agent(root, [correction, PASS], root / "illustrations", max_redraws=2)
            self.assertEqual(count, 1)
            self.assertEqual(load_bundle(manifest)["figures"][0]["image_attempts"], 3)
            self.assertEqual(sum(not c.get("reused_from_previous_run") for c in model.calls), 2)

    def test_major_design_defect_stops_before_image_billing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "major issues"):
                self.run_agent(root, [ANALYSIS, PLAN, FAIL, PLAN, FAIL])
            self.assertEqual(json.loads((root / "illustrations/manifest.json").read_text())["status"], "failed")
            self.assertFalse(list((root / "illustrations").glob("*.png")))

    def test_repeated_geometry_failures_trigger_one_smaller_replanned_graph(self):
        correction = {"prompt": compile_prompt(PLAN["figures"][0])}
        with tempfile.TemporaryDirectory() as directory:
            manifest, count, _ = self.run_agent(Path(directory),
                [ANALYSIS, PLAN, PASS, FAIL, correction, FAIL, PLAN, PASS, PASS], simplify=True)
            self.assertEqual(count, 3)
            figure = load_bundle(manifest)["figures"][0]
            self.assertIn("simplified", figure["image"])
            self.assertEqual(figure["image_attempts"], 3)

    def test_tampered_image_and_outside_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _, _ = self.run_agent(Path(directory))
            bundle = load_bundle(manifest)
            image = manifest.parent / bundle["figures"][0]["image"]
            original = image.read_bytes()
            image.write_bytes(original + b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"): load_bundle(manifest)
            image.write_bytes(original)
            bundle["figures"][0]["image"] = "../outside.png"
            write_json(manifest, bundle)
            with self.assertRaisesRegex(ValueError, "outside bundle"): load_bundle(manifest)

    def test_review_cannot_approve_major_defect(self):
        with self.assertRaisesRegex(ValueError, "major issues"):
            validate_review({**FAIL, "approved": True})

    def test_figure_references_are_resolved_and_unknown_ids_rejected(self):
        citations = {"entries": [], "by_source_id": {}}
        self.assertIn(r"Figure~\ref{fig:evidence_flow}", render_paragraph("See [[figure:evidence_flow]].", {}, citations, figure_ids={"evidence_flow"}))
        with self.assertRaisesRegex(ValueError, "Unknown figure"):
            render_paragraph("See [[figure:invented]].", {}, citations)

    def test_schema_repaired_review_is_the_one_offline_reader_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest, _, _ = self.run_agent(Path(directory), [ANALYSIS, PLAN, PASS, {"wrong": True}, PASS])
            self.assertEqual(load_bundle(manifest)["status"], "reviewed_automatically")

    def test_real_framework_offline_handoff_preserves_figures_and_evidence(self):
        from paper_framework.project import generate_project
        from paper_content.project import fill_project
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_project(MODULE / "examples/memory-research.brief.json", root / "framework", MODULE / "examples/memory-research.literature.json")
            context = build_context(root / "framework")
            context["source_catalog"]["method"] = "Documents are selected and then read."
            with patch("paper_illustration.pipeline.build_context", return_value=context), patch("generate_methodology.generate", side_effect=fake_image):
                manifest = run_illustrations(root / "framework", root / "illustrations", Model([ANALYSIS, PLAN, PASS, PASS]), self.settings(root), review_mode="reviewed")
                content = json.loads((MODULE / "examples/memory-research.content.json").read_text(encoding="utf-8"))
                next(s for s in content["sections"] if s["id"] == "method")["paragraphs"][0] += " The evidence path is illustrated in [[figure:evidence_flow]]."
                write_json(root / "content.json", content)
                with patch("paper_content.model.JsonModel.complete", side_effect=AssertionError("Offline handoff must not call a model")):
                    report = fill_project(root / "framework", root / "paper", content_json=root / "content.json", illustration_manifest=manifest)
                writer = Model([content])
                with patch("paper_content.editorial.draft_and_review", side_effect=AssertionError("Default must not review")):
                    live_report = fill_project(root / "framework", root / "live", model=writer, illustration_manifest=manifest)
                self.assertEqual(live_report["new_text_calls"], 1)
                self.assertEqual(live_report["writing_mode"], "fast")
                self.assertEqual(writer.config["request"], {"max_tokens": 123})
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["calls"], [])
            self.assertTrue((root / "paper/figures/evidence_flow.png").is_file())
            self.assertFalse((root / "paper/figures/methodology.png").exists())
            load_bundle(root / "paper/illustrations/manifest.json")

    def test_fast_default_one_plan_parallel_images_no_review_or_redraw(self):
        from threading import Barrier
        plan = deepcopy(PLAN)
        plan["figures"].append(deepcopy(plan["figures"][0]))
        plan["figures"][1]["id"] = "second_view"
        # Missing redundant prose is compiled from the graph, without schema-repair billing.
        plan["figures"][0]["compact_prompt"] = compile_prompt(plan["figures"][0])
        barrier = Barrier(2)
        def concurrent_image(*args, **kwargs):
            barrier.wait(timeout=5)  # Fails if implementation serializes the independent jobs.
            return fake_image(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = Model([plan])
            with patch("paper_illustration.pipeline.build_context", return_value=CONTEXT), patch("generate_methodology.generate", side_effect=concurrent_image) as images:
                manifest = run_illustrations(root / "framework", root / "illustrations", model, self.settings(root))
            bundle = load_bundle(manifest)
            self.assertEqual(len(model.calls), 1)
            self.assertEqual(images.call_count, 2)
            self.assertEqual(bundle["status"], "generated_unreviewed")
            self.assertEqual(bundle["new_text_tokens"], 10)
            self.assertEqual(bundle["figures"][1]["prompt_origin"], "compiled_from_design")
            self.assertTrue(all(f["visual_review_approved"] is None and f["image_attempts"] == 1 for f in bundle["figures"]))
            with patch("paper_illustration.pipeline.build_context", return_value=CONTEXT), patch("generate_methodology.generate", side_effect=AssertionError("No new billing")):
                resumed = run_illustrations(root / "framework", root / "resumed", Model([]), self.settings(root), resume_from=manifest.parent)
            self.assertEqual(load_bundle(resumed)["new_text_calls"], 0)
            checks = manifest.parent / bundle["figures"][0]["code_checks"]
            checks.write_text("{}")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_bundle(manifest)

    def test_fast_rejects_cycle_before_any_image_billing(self):
        plan = deepcopy(PLAN)
        plan["figures"][0]["compact_prompt"] = compile_prompt(plan["figures"][0])
        plan["figures"][0]["edges"].append({"from": "reader", "to": "docs", "label": "Loop"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("paper_illustration.pipeline.build_context", return_value=CONTEXT), patch("generate_methodology.generate") as images:
                with self.assertRaisesRegex(ValueError, "feedback loops"):
                    run_illustrations(root / "framework", root / "illustrations", Model([plan]), self.settings(root))
            self.assertEqual(images.call_count, 0)


if __name__ == "__main__":
    unittest.main()
