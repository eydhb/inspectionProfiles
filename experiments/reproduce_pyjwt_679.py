"""Exercise the original issue's options mutation, using only local HS256 data.

Exit 0: the desired no-mutation behavior holds.
Exit 1: options were mutated, reproducing the historical bug.
"""

import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(snapshot))
    import jwt

    imported = Path(jwt.__file__).resolve()
    if not imported.is_relative_to(snapshot):
        raise RuntimeError("The imported jwt module did not come from the selected snapshot.")
    options = {"verify_signature": False, "verify_aud": False}
    before = options.copy()
    payload = {"some": "payload"}
    key = "benchmark-fixture-not-a-real-secret"
    token = jwt.encode(payload, key, algorithm="HS256")
    decoded = jwt.decode(token, key, algorithms=["HS256"], options=options)
    passed = options == before
    print(json.dumps({
        "module": imported.relative_to(snapshot).as_posix(),
        "package_version_string": jwt.__version__,
        "options_before": before, "options_after": options,
        "added_keys": sorted(set(options) - set(before)),
        "payload_decoded_correctly": decoded == payload,
        "expected": "The caller's options dictionary remains unchanged",
        "passed": passed,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
