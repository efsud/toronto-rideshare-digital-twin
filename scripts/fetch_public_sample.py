"""Fetch a bounded public SVC speed sample with immutable download evidence."""

import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from toronto_rideshare.manifest import file_checksum
from toronto_rideshare.traffic.public_data import PACKAGE_ID


def main():
    target = Path("data/raw")
    target.mkdir(parents=True, exist_ok=True)
    api = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show"
    response = requests.get(api, params={"id": PACKAGE_ID}, timeout=45)
    response.raise_for_status()
    metadata = response.json()["result"]
    resource = next(r for r in metadata["resources"] if r["name"] == "svc_raw_data_speed_2025_2029")
    path = target / "midblock_speed_sample.csv"
    with requests.get(resource["url"], stream=True, timeout=45) as response:
        response.raise_for_status()
        lines = list(itertools.islice(response.iter_lines(), 50001))
    path.write_bytes(b"\n".join(lines) + b"\n")
    (target / "midblock_provenance.json").write_text(
        json.dumps(
            {
                "url": resource["url"],
                "resource_id": resource["id"],
                "retrieved_at": datetime.now(UTC).isoformat(),
                "sha256": file_checksum(path),
                "rows": len(lines) - 1,
                "license": metadata.get("license_title"),
                "sampling": "First 50,000 records, not random",
            },
            indent=2,
        )
    )
    print(path)


if __name__ == "__main__":
    main()
