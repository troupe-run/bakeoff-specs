Fixed technical constraints for this project:
- Python 3.12 or later, managed with uv. The CLI must run as `uv run troupe config …` from the repository root.
- Use the `eventsourcing` library for the event store and projection.
- Configuration lives in `<theatre>/.troupe/troupe.yml` (or `.yaml`).
