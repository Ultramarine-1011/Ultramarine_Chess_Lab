"""Compare final retained R1/R2-reference queries, excluding platform timing."""
import json
from pathlib import Path

here = Path(__file__).resolve().parent
record = json.loads((here.parent / "r1-r2-benchmark-final-20261015/record.json").read_text())
rows = {(r["engine"], r["position"], json.dumps(r["limit"], sort_keys=True), r["repeat"]): r for r in record["rows"]}
fields = ["depth", "score_cp", "nodes", "move", "pv"]
compared = 0
for key, row in rows.items():
    if key[0] == "R1":
        reference = rows[("R2-reference", *key[1:])]
        for field in fields:
            assert row[field] == reference[field], (key, field, row[field], reference[field])
        compared += 1
assert compared == 60, compared
print(f"R1/R2-reference: {compared} queries, {fields}, zero mismatches")
