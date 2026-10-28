"""Settlement-time estimate from a static lookup table (data/settlement_table.json)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from models import ClaimType, Settlement

TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "settlement_table.json"


@lru_cache(maxsize=1)
def load_table(path: Path = TABLE_PATH) -> dict[str, list[int]]:
    with path.open(encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def estimate(claim_type: ClaimType, cashless: bool, docs_complete: bool) -> Settlement:
    route = "cashless" if cashless else "reimbursement"
    key = f"{claim_type}|{route}|{str(docs_complete).lower()}"
    min_days, max_days = load_table()[key]
    return Settlement(
        min_days=min_days, max_days=max_days, route=route, docs_complete=docs_complete
    )
