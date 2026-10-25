"""Per-entity high-water mark: the newest `aktualisiert` seen in a successful run.

Incremental runs start from the watermark (minus an overlap) instead of re-reading all data.
Watermarks live next to the data, in ``state/watermarks/<entity>.json`` in the bucket, and
only ever move forward.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime

from ingestion.storage import ObjectStore


def watermark_key(entity: str) -> str:
    """Return the object key that holds the watermark of `entity`."""
    return f"state/watermarks/{entity}.json"


@dataclass(frozen=True)
class Watermark:
    """How far ingestion of one entity has got.

    Attributes:
        entity: DIP entity, e.g. ``"vorgang"``.
        max_aktualisiert: Newest ``aktualisiert`` of any record fetched by a successful run
            (timezone-aware, in the offset DIP returned).
        last_run_id: Run that set this value.
        updated_at: When the watermark was written.
    """

    entity: str
    max_aktualisiert: datetime
    last_run_id: str
    updated_at: datetime

    def to_json(self) -> bytes:
        """Serialize to UTF-8 JSON with ISO-8601 timestamps."""
        data = asdict(self)
        for field in ("max_aktualisiert", "updated_at"):
            data[field] = data[field].isoformat()
        return json.dumps(data, indent=2).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> "Watermark":
        """Parse the output of `to_json`."""
        data = json.loads(raw)
        return cls(
            entity=data["entity"],
            max_aktualisiert=datetime.fromisoformat(data["max_aktualisiert"]),
            last_run_id=data["last_run_id"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


def load_watermark(store: ObjectStore, entity: str) -> Watermark | None:
    """Return the stored watermark of `entity`, or None if no run has succeeded yet."""
    raw = store.get(watermark_key(entity))
    return Watermark.from_json(raw) if raw is not None else None


def advance_watermark(store: ObjectStore, new: Watermark) -> Watermark:
    """Store `new` unless the stored watermark is already as late or later.

    Keeping watermarks monotonic means a backfill of an old window can never make the next
    incremental run re-read (or worse, skip) data.

    Args:
        store: Where watermarks are kept.
        new: Candidate watermark from a run that just succeeded.

    Returns:
        The watermark now in effect: `new`, or the existing later one.
    """
    current = load_watermark(store, new.entity)
    if current is not None and current.max_aktualisiert >= new.max_aktualisiert:
        return current
    store.put(watermark_key(new.entity), new.to_json())
    return new
