"""Load the synthetic wallet (users, vehicles, policies, documents) from data/*.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from models import Document, Policy, User, Vehicle

DATA_DIR = Path(__file__).resolve().parent / "data"


class Wallet(BaseModel):
    users: dict[str, User]
    vehicles: dict[str, Vehicle]
    policies: dict[str, Policy]
    documents: dict[str, Document]

    def vehicles_for(self, user_id: str) -> list[Vehicle]:
        return [v for v in self.vehicles.values() if v.user_id == user_id]

    def policies_for(self, user_id: str) -> list[Policy]:
        return [p for p in self.policies.values() if p.user_id == user_id]


@lru_cache(maxsize=1)
def load_wallet(data_dir: Path = DATA_DIR) -> Wallet:
    users_raw = json.loads((data_dir / "users.json").read_text(encoding="utf-8"))
    policies_raw = json.loads((data_dir / "policies.json").read_text(encoding="utf-8"))
    documents_raw = json.loads((data_dir / "documents.json").read_text(encoding="utf-8"))
    return Wallet(
        users={u["id"]: User(**u) for u in users_raw["users"]},
        vehicles={v["id"]: Vehicle(**v) for v in users_raw["vehicles"]},
        policies={p["id"]: Policy(**p) for p in policies_raw},
        documents={d["document_code"]: Document(**d) for d in documents_raw},
    )
