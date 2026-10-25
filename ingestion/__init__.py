"""Extract data from the Bundestag DIP API and land it, unmodified, in the Bronze layer.

Modules:
    client: HTTP client for the DIP API (auth, cursor paging, retries).
    extract: One idempotent extraction run of one entity into Bronze.
    watermark: Per-entity high-water mark used by incremental runs.
    storage: Object storage backends (S3 / RustFS, and in-memory for tests).
    config: Settings read from environment variables.

Run ``python -m ingestion --help`` for the command line interface.
"""

ENTITIES = (
    "vorgang",
    "vorgangsposition",
    "drucksache",
    "plenarprotokoll",
    "aktivitaet",
    "person",
)
"""DIP list endpoints we ingest, in the order runs process them."""
