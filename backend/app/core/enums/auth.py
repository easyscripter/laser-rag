"""Authentication/authorization enumerations (spec §6, §11)."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Access role carried in the JWT and enforced by dependency guards."""

    READER = "reader"  # may read/search/chat
    CURATOR = "curator"  # may additionally ingest and manage documents
