"""Consent-bound, scoped memory primitives for personal agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any, Callable, Dict, List, Literal, Optional


MemoryKind = Literal["profile", "fact"]


class ConsentRequiredError(PermissionError):
    """Raised when a personal memory write lacks explicit consent."""


@dataclass(frozen=True)
class MemoryConsent:
    """The explicit permission under which a memory item was retained."""

    granted: bool
    purpose: str
    granted_at: datetime
    source: str = "user"


@dataclass(frozen=True)
class MemoryProvenance:
    """Origin metadata that makes a retained value auditable."""

    source: str
    reference: Optional[str] = None
    observed_at: Optional[datetime] = None


@dataclass(frozen=True)
class PersonalMemoryItem:
    """One scoped, consent-bound profile attribute or fact."""

    id: str
    subject_id: str
    scope: str
    kind: MemoryKind
    key: str
    value: Any
    consent: MemoryConsent
    provenance: MemoryProvenance
    created_at: datetime
    expires_at: Optional[datetime] = None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= datetime.now(timezone.utc)


class ScopedPersonalMemory:
    """In-memory personal memory, isolated by subject and caller-defined scope.

    Values are never shared across scopes. Callers must supply explicit consent and
    provenance for every write. A clock may be injected to make expiry deterministic.
    """

    def __init__(self, *, now: Optional[Callable[[], datetime]] = None):
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._items: Dict[str, PersonalMemoryItem] = {}
        self._lock = RLock()
        self._next_id = 0

    def remember_profile(
        self, subject_id: str, scope: str, key: str, value: Any, *, consent: MemoryConsent,
        provenance: MemoryProvenance, ttl: Optional[timedelta] = None,
    ) -> PersonalMemoryItem:
        return self._remember("profile", subject_id, scope, key, value, consent, provenance, ttl)

    def remember_fact(
        self, subject_id: str, scope: str, key: str, value: Any, *, consent: MemoryConsent,
        provenance: MemoryProvenance, ttl: Optional[timedelta] = None,
    ) -> PersonalMemoryItem:
        return self._remember("fact", subject_id, scope, key, value, consent, provenance, ttl)

    def get(self, subject_id: str, scope: str, key: str, *, kind: Optional[MemoryKind] = None) -> Optional[PersonalMemoryItem]:
        with self._lock:
            self._purge_expired()
            matches = [
                item for item in self._items.values()
                if item.subject_id == subject_id and item.scope == scope and item.key == key
                and (kind is None or item.kind == kind)
            ]
            return max(matches, key=lambda item: item.created_at, default=None)

    def list(self, subject_id: str, scope: str, *, kind: Optional[MemoryKind] = None) -> List[PersonalMemoryItem]:
        with self._lock:
            self._purge_expired()
            return [
                item for item in self._items.values()
                if item.subject_id == subject_id and item.scope == scope and (kind is None or item.kind == kind)
            ]

    def forget(self, subject_id: str, scope: str, *, key: Optional[str] = None, kind: Optional[MemoryKind] = None) -> int:
        """Permanently remove matching memories and return their count."""
        with self._lock:
            ids = [
                item_id for item_id, item in self._items.items()
                if item.subject_id == subject_id and item.scope == scope
                and (key is None or item.key == key) and (kind is None or item.kind == kind)
            ]
            for item_id in ids:
                del self._items[item_id]
            return len(ids)

    def _remember(
        self, kind: MemoryKind, subject_id: str, scope: str, key: str, value: Any,
        consent: MemoryConsent, provenance: MemoryProvenance, ttl: Optional[timedelta],
    ) -> PersonalMemoryItem:
        if not consent.granted:
            raise ConsentRequiredError("Personal memory requires explicit granted consent.")
        if not subject_id or not scope or not key:
            raise ValueError("subject_id, scope, and key must be non-empty.")
        if ttl is not None and ttl <= timedelta(0):
            raise ValueError("ttl must be positive when provided.")
        with self._lock:
            self._purge_expired()
            now = self._now()
            self._next_id += 1
            item = PersonalMemoryItem(
                id=f"memory-{self._next_id}", subject_id=subject_id, scope=scope, kind=kind,
                key=key, value=value, consent=consent, provenance=provenance,
                created_at=now, expires_at=now + ttl if ttl else None,
            )
            self._items[item.id] = item
            return item

    def _purge_expired(self) -> None:
        now = self._now()
        for item_id, item in list(self._items.items()):
            if item.expires_at is not None and item.expires_at <= now:
                del self._items[item_id]
