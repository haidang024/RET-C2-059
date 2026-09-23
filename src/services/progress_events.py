"""Best-effort progress events for long-running provider calls."""

from __future__ import annotations

from typing import Any


def emit_progress(message: str, metadata: dict[str, Any] | None = None) -> None:
    """Emit Marketplace progress without coupling module import to runtime setup."""
    try:
        from shared.services.events import EventType, emitter

        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message=message,
            metadata=metadata or {},
        )
    except Exception:
        # Progress telemetry must never change the business result.
        return
