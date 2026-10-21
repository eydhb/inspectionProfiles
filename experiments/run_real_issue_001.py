"""Run the frozen historical localization case without modifying CodeLens.

Use the existing CodeLens environment. A separate output directory is required
for a replay, so the first attempt's evidence cannot be silently overwritten.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile
import time

CASE_DIR = Path(__file__).resolve().parent / "real_issue_001"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def git(repository, *args):
    # Git for Windows may otherwise convert archive text to CRLF.
    # A benchmark snapshot must match the stored blobs byte for byte.
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(repository), *args])


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export_snapshot(history, commit, target):
    if target.exists():
        raise ValueError("Snapshot destination already exists; choose a fresh workspace.")
    raw = git(history, "archive", "--format=tar", commit)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as bundle:
        for member in bundle:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or "\\" in member.name:
                raise ValueError("Unsafe archive path")
            output = target.joinpath(*name.parts)
            if member.isdir():
                output.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                output.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as content:
                    output.write_bytes(content.read())
            else:
                raise ValueError("Only regular files and directories are supported.")
    manifest = [
        {"path": path.relative_to(target).as_posix(),
         "sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
        for path in sorted(target.rglob("*")) if path.is_file()
    ]
    expected = {
        line.split("\t", 1)[1]: line.split()[2]
        for line in git(history, "ls-tree", "-r", commit).decode().splitlines()
    }
    if {row["path"] for row in manifest} != set(expected):
        raise AssertionError("Snapshot file set differs from the Git tree")
    for row in manifest:
        raw = (target / row["path"]).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected[row["path"]]:
            raise AssertionError("Snapshot content differs from the Git blob")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codelens", type=Path, required=True, help="Local CodeLens Git repository root")
    parser.add_argument("--history", type=Path, required=True, help="A local clone of jpadilla/pyjwt")
    parser.add_argument("--workspace", type=Path, required=True, help="Scratch space outside the output directory")
    parser.add_argument("--output-dir", type=Path, default=CASE_DIR)
    args = parser.parse_args()
    PROJECT = args.codelens.resolve() / "outputs" / "issue-locator"
    if not (PROJECT / "issue_locator" / "agent.py").is_file():
        raise ValueError("--codelens must point to the CodeLens Git repository root")
    sys.path.insert(0, str(PROJECT))
    from issue_locator.agent import MAX_READS, MAX_STEPS, analyze
    from issue_locator.repository import Repository
    case = json.loads((CASE_DIR / "case.json").read_text(encoding="utf-8"))
    prompt_bytes = (CASE_DIR / "input.txt").read_bytes()
    issue = prompt_bytes.decode("utf-8").strip()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "run_metadata.json").exists() or (output / "agent_result.json").exists():
        raise ValueError("Existing run evidence found. Use a new --output-dir for a replay.")
    workspace = args.workspace.resolve()
    if workspace == output or workspace.is_relative_to(output) or output.is_relative_to(workspace):
        raise ValueError("Workspace and output directory must be separate.")
    (output / "case.json").write_bytes((CASE_DIR / "case.json").read_bytes())
    (output / "input.txt").write_bytes(prompt_bytes)
    before = case["before_commit"]
    fix = case["fix_commit"]
    assert git(args.history, "rev-parse", fix + "^1").decode().strip() == before
    # Pin the implementation, not merely the current HEAD label.
    code_hashes = {}
    for name in ["agent.py", "repository.py", "model.py", "__init__.py"]:
        current = (PROJECT / "issue_locator" / name).read_bytes()
        pinned = git(PROJECT, "show", case["agent_commit"] + ":outputs/issue-locator/issue_locator/" + name)
        assert current.replace(b"\r\n", b"\n") == pinned.replace(b"\r\n", b"\n"), name
        code_hashes[name] = digest(current)
    started = now()
    snapshot = workspace / "before"
    manifest = export_snapshot(args.history, before, snapshot)
    repository = Repository(snapshot)
    visible = repository.list_files()
    save(output / "snapshot_manifest.json", manifest)
    save(output / "visible_files.json", visible)
    metadata = {
        "status": "started", "started_at": started, "attempt": 1,
        "case_file_sha256": digest((CASE_DIR / "case.json").read_bytes()),
        "input_file_sha256": digest(prompt_bytes),
        "effective_input_sha256": digest(issue.encode("utf-8")),
        "before_commit": before, "before_tree": git(args.history, "rev-parse", before + "^{tree}").decode().strip(),
        "fix_commit": fix, "agent_commit": case["agent_commit"],
        "agent_source_sha256": code_hashes, "mode": "offline",
        "python": platform.python_version(), "platform": platform.platform(),
        "langgraph": importlib.metadata.version("langgraph"),
        "max_steps": MAX_STEPS, "max_reads": MAX_READS,
        "snapshot_files": len(manifest), "visible_files": len(visible["files"]),
        "visible_list_truncated": visible["truncated"],
        "snapshot_manifest_sha256": digest((output / "snapshot_manifest.json").read_bytes()),
        "result_path": "agent_result.json",
        "notes": "One primary run; no model/network tools; an unchanged pre-fix tree is the only analysis root.",
    }
    save(output / "run_metadata.json", metadata)
    tick = time.monotonic()
    # This is the sole localization call. No ground-truth information is passed.
    result = analyze(repository, issue, mode="offline")
    save(output / "agent_result.json", result)
    assert result["issue"] == issue
    citations = 0
    for candidate in result["candidates"]:
        lines = (snapshot / candidate["path"]).read_text(encoding="utf-8-sig").splitlines()
        for evidence in candidate["evidence"]:
            assert lines[evidence["line"] - 1] == evidence["text"]
            citations += 1
    for row in manifest:
        assert digest((snapshot / row["path"]).read_bytes()) == row["sha256"]
    # Only after the raw answer is written, derive labels from the fix delta.
    changed = git(args.history, "diff", "--name-only", before, fix).decode().splitlines()
    production = [path for path in changed if path.startswith("jwt/") and path.endswith(".py")]
    tests = [path for path in changed if path.startswith("tests/")]
    assert production and set(changed) == set(production + tests)
    predicted = list(dict.fromkeys(c["path"] for c in result["candidates"]))
    metrics = {
        "metric": "exact-path any-hit at k", "sample_count": 1,
        "ground_truth_production_files": production, "changed_test_files": tests,
        "all_changed_files": changed, "candidate_paths_in_original_order": predicted,
        "first_relevant_rank": next((i for i, p in enumerate(predicted, 1) if p in production), None),
        "top_1_hit": bool(set(predicted[:1]) & set(production)),
        "top_3_hit": bool(set(predicted[:3]) & set(production)),
        "top_1_matches": [p for p in predicted[:1] if p in production],
        "top_3_matches": [p for p in predicted[:3] if p in production],
        "verified_evidence_rows": citations,
        "note": "Single-case file localization, not line localization, root-cause accuracy, or population accuracy.",
    }
    save(output / "metrics.json", metrics)
    (output / "fix.patch").write_bytes(git(args.history, "diff", "--no-ext-diff", before, fix))
    (output / "upstream-LICENSE.txt").write_bytes(git(args.history, "show", before + ":LICENSE"))
    metadata.update(
        status="complete", completed_at=now(), wall_seconds=round(time.monotonic() - tick, 3),
        result_sha256=digest((output / "agent_result.json").read_bytes()),
        snapshot_unchanged=True, tool_calls=len(result["trace"]),
    )
    save(output / "run_metadata.json", metadata)
    print(json.dumps({"metadata": metadata, "metrics": metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
