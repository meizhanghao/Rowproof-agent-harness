"""Check a candidate against current public GitHub repository search."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="rowproof-agent-harness")
    parser.add_argument("--output", type=Path, default=Path("docs/name-check-latest.json"))
    args = parser.parse_args()
    url = "https://api.github.com/search/repositories?" + urlencode(
        {
            "q": args.name + " in:name",
            "per_page": 100,
        }
    )
    request = Request(
        url, headers={"User-Agent": "rowproof-name-check", "Accept": "application/vnd.github+json"}
    )
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("incomplete_results") or data.get("total_count", 0) > 100:
        raise SystemExit("Search incomplete/too broad; inspect the result before concluding.")
    matches = [
        item["full_name"]
        for item in data.get("items", [])
        if item["name"].casefold() == args.name.casefold()
    ]
    record = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "scope": "public GitHub repositories, at lookup time only",
        "query_total_count": data.get("total_count"),
        "exact_name_matches": matches,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 1 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
