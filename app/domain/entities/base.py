"""Entidades base del dominio."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BaseEntity:
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
