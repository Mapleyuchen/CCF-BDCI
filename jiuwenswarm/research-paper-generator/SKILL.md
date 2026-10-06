---
name: research-paper-generator
description: Generate and revise an evidence-grounded ICLR manuscript from completed JiuwenSwarm memory experiments, retrieve arXiv metadata, create a DashScope methodology illustration, compile PDF, and check traceability. Use for this project's paper workflow, not autonomous invention of experiments or results.
---

# Evidence-grounded paper workflow

Run commands from the repository root. See [API workflow](references/api_workflow.md) for endpoints, environment variables, model choice, image tasks, arXiv configuration and recovery commands. See [illustration agent](references/illustration_agent.md) for research analysis, diagram contracts, visual review and replay. See [module README](README.md) for brief, literature and content schemas.

## Establish the evidence

- Revised experiments live in `experiments/MEMORY_EVAL_V2.md`. After the entire scored run validates, `finalize_memory_eval_handoff.py` produces `examples/memory-eval-v2.brief.json` and self-contained `controlled_memory_eval_live` comparisons. Use that brief with the **general** renderer; the legacy L1 research-profile assets are incompatible with its token budgets and frozen full-history bank. If these files are absent, treat the revision experiments as unfinished, never substitute pilot values.
- The v2 adapter verifies semantic-label provenance and recomputes memory-cluster intervals, including failed questions in the denominator. It preserves selector names and `context_tokens`; it does not interpret token caps as `context_chars`. Reuse uses measured distinct-query prefixes. Human adjudication remains required, and the substituted judge/subset protocol is not an official LongMemEval score.

- Use `examples/memory-research.brief.json` and `memory-research.literature.json` for the current study. The research profile is specific to the audited `jiuwenswarm_l1_v1` implementation; do not reuse its equations or schematic for another implementation without revising `research_assets.py`.
- Inputs must be live `records` and `runs` with model identity, dataset hash, isolated question history and verified memory injection. `paper_content/evidence.py` recomputes paired metrics and includes recorded memory-write cost. Do not substitute legacy simulated output or self-test results.
- Current evidence is a selected twenty-question slice at two budgets, with one run per budget, using qwen-plus. Changing the writing model does not re-run these experiments or change their model identity. Budget sensitivity is not component ablation; L2/L3 persistence and team synchronization have not been evaluated.
- Before adding Related Work claims, retrieve real metadata and read relevant source material. The arXiv API has no key; enforce a single connection and at least three seconds between requests. Save the raw-response cache and provenance. Fixed literature aliases used in a brief must continue to match citation IDs.

## Generate and revise

```powershell
python jiuwenswarm/research-paper-generator/scripts/write_paper.py --generate-illustrations --max-figures 2 --output output/research-new --compile
```

The default is fast: one DashScope `qwen3.8-max` call combines research analysis, source-linked diagram design and final compact prompts. Each diagram has at most seven nodes, an acyclic graph and an exact text whitelist. Submit one `qwen-image-3.0-pro` task per figure, concurrently; do not automatically review or redraw. Save prompts, task provenance, hashes, elapsed time and returned usage. Mark the result `generated_unreviewed`; code validation is not visual certification. Results plots come from Matplotlib and experiment records, never from image generation.

Default writing uses one manuscript call, with at most one repair only for a concrete schema/token failure. The writer explains every figure using `[[figure:ID]]`. Two diagrams normally require two text requests and two image tasks total. `--illustration-manifest <run>/illustrations/manifest.json` reuses a recorded bundle, including offline `--content-json` replay. Changed evidence or artifact hashes fail validation. Only explicit `--review-mode reviewed` enables model design/visual reviews and the four writing stages; redraw additionally requires `--max-redraws 1` or `2`. The low-level `generate_methodology.py --prompt ...` remains a debugging entry point.

The writer returns section JSON. Numbers and citations use known `[[metric:...]]` / `[[cite:...]]` tokens; the renderer owns LaTeX, equations, tables, references and numeric formatting. Do not weaken validation to accept fabricated metrics. Model review does not replace scientific review.

For an interrupted reviewed writing run, pass `--review-mode reviewed --resume-from <old-run>/paper` and a new output directory. Saved stages require identical instructions and evidence. For illustration-stage resume use `--illustration-resume-from`; for low-level image tasks use `--resume-task`. Never create a duplicate paid task automatically or silently fall back to a placeholder/provider.

For purely offline rendering, use `fill_content.py --content-json` with saved validated prose and the reviewed image; see the API guide. Keep credentials in environment variables or an explicitly chosen private env file, never in outputs or submission materials.

## Review the actual artifact

1. Read the revised prose against normalized records and cited sources. Check cost ratios, matched-pair interpretation, partial-evidence cases and baseline formatting confounds. Do not claim significance from Wilson intervals or combine reused questions as independent samples.
2. Run compilation and `check_quality.py`. Mechanical success covers file/format consistency, not novelty, causal inference or publication quality.
3. Render every final PDF page and inspect equations, tables, labels, floats, bibliography and appendix. Fix the source and rebuild when layout is defective.
4. Deliver the PDF with corresponding source, stage outputs, API provenance and evidence hashes. Preserve `human_review_required: true` until an actual human review is supplied. Submission readiness additionally needs the real team identity, paper-bound Reviewer Token and upstream PR required by the supplied competition template.

Do not use `generate_paper.py`, `run_baseline_experiments.py`, `run_enhanced_experiments.py` or `compare_results.py` for research evidence: those are legacy demonstration paths. This CLI workflow is not yet registered as a tool in the main conversational Agent.
