"""Fit rider price response only from explicitly identified acceptance records."""

import argparse
import json
from pathlib import Path

import pandas as pd

from toronto_rideshare.calibration import fit_rider_response
from toronto_rideshare.manifest import file_checksum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="CSV: group_id, price_cad, accepted, offered")
    parser.add_argument(
        "--source", required=True, help="Dataset/source description; not a validity badge"
    )
    parser.add_argument("--synthetic", action="store_true", help="Mark recovery tests as synthetic")
    parser.add_argument("--output", default="results/rider_calibration.json")
    args = parser.parse_args()
    report = fit_rider_response(pd.read_csv(args.input))
    report["provenance"] = {
        "source": args.source,
        "input_sha256": file_checksum(args.input),
        "data_kind": "synthetic" if args.synthetic else "user_supplied_observations",
    }
    if args.synthetic:
        report["status"] = "synthetic_recovery_check_not_empirical_calibration"
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(path)


if __name__ == "__main__":
    main()
