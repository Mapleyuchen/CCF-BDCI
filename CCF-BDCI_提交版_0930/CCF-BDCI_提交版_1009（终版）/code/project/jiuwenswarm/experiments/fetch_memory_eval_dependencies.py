"""Download the pinned public benchmark, scorer and tokenizer; verify every hash."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent

def download(url, path, expected=None):
    if path.is_file() and (expected is None or hashlib.sha256(path.read_bytes()).hexdigest() == expected):
        print(f"Verified: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    sha = hashlib.sha256()
    with urlopen(url, timeout=120) as response, temporary.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            sha.update(chunk)
            out.write(chunk)
    if expected and sha.hexdigest() != expected:
        temporary.unlink()
        raise ValueError(f"Hash mismatch for {path.name}")
    temporary.replace(path)
    print(f"Downloaded and verified: {path.relative_to(ROOT)}")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-dataset", action="store_true")
    args = p.parse_args()
    deps = json.loads((ROOT / "data/memory_eval_dependencies_v2.json").read_text())
    revision = deps["tokenizer_revision"]
    for name, sha in deps["tokenizer_files"].items():
        download(f"https://huggingface.co/{deps['tokenizer_repo']}/resolve/{revision}/{name}",
                 ROOT / "data/public/qwen3_tokenizer" / name, sha)
    commit = deps["longmemeval_commit"]
    base = f"https://raw.githubusercontent.com/xiaowu0162/LongMemEval/{commit}/"
    download(base + "src/evaluation/evaluate_qa.py", ROOT / "data/public/longmemeval_protocol/evaluate_qa.py", deps["scorer_sha256"])
    download(base + "LICENSE", ROOT / "data/public/longmemeval_protocol/LICENSE")
    if not args.skip_dataset:
        protocol = json.loads((ROOT / "data/memory_eval_protocol_v2.json").read_text())
        download(protocol["source_url"], ROOT / "data/public/longmemeval_s_cleaned.json", protocol["source_sha256"])

if __name__ == "__main__":
    main()
