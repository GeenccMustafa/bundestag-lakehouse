"""Per-entity high-water mark: the newest `aktualisiert` seen in a successful run."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from ingestion.storage import ObjectStore


def watermark_key(entity: str) -> str:
    return f"state/watermarks/{entity}.json"


@dataclass(frozen=True)
class Watermark:
    entity: str
    max_aktualisiert: datetime  # timezone-aware
    last_run_id: str
    updated_at: datetime

    def to_json(self) -> bytes:
        data = asdict(self)
        for field in ("max_aktualisiert", "updated_at"):
            data[field] = data[field].isoformat()
        return json.dumps(data, indent=2).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> "Watermark":
        data = json.loads(raw)
        return cls(
            entity=data["entity"],
            max_aktualisiert=datetime.fromisoformat(data["max_aktualisiert"]),
            last_run_id=data["last_run_id"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


def load_watermark(store: ObjectStore, entity: str) -> Watermark | None:
    raw = store.get(watermark_key(entity))
    return Watermark.from_json(raw) if raw is not None else None


def advance_watermark(store: ObjectStore, new: Watermark) -> Watermark:
    """Persist `new` unless the stored watermark is already later (watermarks never go back)."""
    current = load_watermark(store, new.entity)
    if current is not None and current.max_aktualisiert >= new.max_aktualisiert:
        return current
    store.put(watermark_key(new.entity), new.to_json())
    return new
