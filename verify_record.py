"""Verify saved benchmark evidence without installing CodeLens or calling a model."""

import argparse
import hashlib
import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=Path(__file__).parent / "experiments" / "real_issue_001")
    parser.add_argument("--snapshot", type=Path, help="Optional exact pre-fix source snapshot for line verification")
    args = parser.parse_args()
    directory = args.record.resolve()
    metadata = read_json(directory / "run_metadata.json")
    result = read_json(directory / "agent_result.json")
    metrics = read_json(directory / "metrics.json")
    case = read_json(directory / "case.json")
    manifest = read_json(directory / "snapshot_manifest.json")
    for name, key in [
        ("case.json", "case_file_sha256"),
        ("input.txt", "input_file_sha256"),
        ("agent_result.json", "result_sha256"),
        ("snapshot_manifest.json", "snapshot_manifest_sha256"),
    ]:
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        check(actual == metadata[key], f"Hash mismatch: {name}")
    check(result["issue"] == (directory / "input.txt").read_text(encoding="utf-8").strip(), "Input mismatch")
    check(metadata["before_commit"] == case["before_commit"], "Pre-fix commit mismatch")
    check(metadata["fix_commit"] == case["fix_commit"], "Fix commit mismatch")
    check(result["mode"] == metadata["mode"] == case["mode"], "Mode mismatch")
    check(len(result["trace"]) == metadata["tool_calls"], "Tool call count mismatch")
    predicted = list(dict.fromkeys(row["path"] for row in result["candidates"]))
    truth = set(metrics["ground_truth_production_files"])
    check(predicted == metrics["candidate_paths_in_original_order"], "Candidate order mismatch")
    for k in (1, 3):
        hits = [path for path in predicted[:k] if path in truth]
        check(bool(hits) == metrics[f"top_{k}_hit"], f"Top-{k} score mismatch")
        check(hits == metrics[f"top_{k}_matches"], f"Top-{k} paths mismatch")
    first = next((i for i, path in enumerate(predicted, 1) if path in truth), None)
    check(first == metrics["first_relevant_rank"], "First relevant rank mismatch")
    if (directory / "reproduction.json").exists():
        reproduction = read_json(directory / "reproduction.json")
        check(reproduction["before"]["commit"] == case["before_commit"], "Reproduction before commit mismatch")
        check(reproduction["after"]["commit"] == case["fix_commit"], "Reproduction after commit mismatch")
        check(reproduction["before"]["passed"] is False, "Historical reproduction should fail")
        check(reproduction["after"]["passed"] is True, "Fixed reproduction should pass")
    evidence_rows = sum(len(row["evidence"]) for row in result["candidates"])
    check(evidence_rows == metrics["verified_evidence_rows"], "Evidence count mismatch")
    if args.snapshot:
        snapshot = args.snapshot.resolve(strict=True)
        expected = {row["path"] for row in manifest}
        actual = {path.relative_to(snapshot).as_posix() for path in snapshot.rglob("*") if path.is_file()}
        check(actual == expected, "Snapshot file list mismatch")
        for row in manifest:
            path = (snapshot / row["path"]).resolve(strict=True)
            check(path.is_relative_to(snapshot), "Invalid snapshot path")
            check(hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], f"Snapshot hash mismatch: {row['path']}")
        for candidate in result["candidates"]:
            lines = (snapshot / candidate["path"]).read_text(encoding="utf-8-sig").splitlines()
            for row in candidate["evidence"]:
                check(lines[row["line"] - 1] == row["text"], "Source evidence mismatch")
    print(json.dumps({
        "verified": True, "candidates": len(predicted),
        "tool_calls": len(result["trace"]), "evidence_rows": evidence_rows,
        "top_1_hit": metrics["top_1_hit"], "top_3_hit": metrics["top_3_hit"],
        "source_snapshot_verified": bool(args.snapshot),
        "scope": "Integrity and metric checks; not an independent accuracy estimate",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
