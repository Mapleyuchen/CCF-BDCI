"""Save exact protocol-hashed execution sources and local dependency versions."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil

ROOT = Path(__file__).resolve().parent

def archive_sources(run):
    manifest = json.loads((run / "run_manifest.json").read_text())
    locations = [ROOT, ROOT / "memory_eval", ROOT.parent / "jiuwenswarm/agents/harness/common/memory",
                 ROOT.parent / "jiuwenswarm/agents/harness/common/rails"]
    target = run / "code_snapshot"
    target.mkdir(exist_ok=True)
    for name, expected in manifest["code_hashes"].items():
        source = next((directory / name for directory in locations if (directory / name).is_file()), None)
        if source is None or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Source changed since experiment began: {name}")
        shutil.copyfile(source, target / name)
    versions = {name: importlib.metadata.version(name) for name in
                ("openjiuwen", "numpy", "matplotlib", "tokenizers", "openai", "PyYAML", "python-dotenv")}
    (run / "environment.json").write_text(json.dumps(dict(python=platform.python_version(),
        platform=platform.platform(), packages=versions), indent=2), encoding="utf-8")
    supplementary = [ROOT / "memory_eval" / name for name in
        ("scoring.py", "statistics.py", "reporting.py")]
    supplementary += [ROOT / name for name in ("score_memory_eval.py", "score_memory_eval_stream.py",
        "finalize_memory_eval_handoff.py", "archive_memory_eval_code.py")]
    supplementary += [ROOT.parent / "jiuwenswarm/agents/harness/common/rails/enhanced_memory_rail.py",
        ROOT.parent / "jiuwenswarm/agents/harness/common/memory/multi_level_memory.py",
        ROOT.parent / "research-paper-generator/scripts/paper_content/controlled_evidence.py"]
    extra = run / "supplementary_code_snapshot"
    hashes = {}
    for source in supplementary:
        relative = source.relative_to(ROOT.parent)
        destination = extra / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in ("longmemeval_s_turn20_v1.json", "memory_agent_qa_v2.json"):
        source = ROOT / "data" / name
        destination = run / "supplementary_data" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes["data/" + name] = hashlib.sha256(source.read_bytes()).hexdigest()
    (run / "supplementary_snapshot.json").write_text(json.dumps(dict(
        note="Final reproducibility snapshot. Execution hashes were frozen in run_manifest before generation; supplementary hashes record the final scoring/reporting and source data files.",
        sha256=hashes), indent=2), encoding="utf-8")
    print(f"Archived {len(manifest['code_hashes'])} verified sources: {target}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=ROOT / "results/memory_eval_v2")
    args = p.parse_args()
    archive_sources(args.run)

if __name__ == "__main__":
    main()
