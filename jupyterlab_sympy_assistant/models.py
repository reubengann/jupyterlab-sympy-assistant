from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EquationRecord:
    id: str
    name: str
    sympy: str
    latex: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EquationRecord":
        return cls(
            id=str(raw.get("id") or uuid4()),
            name=str(raw.get("name") or "").strip(),
            sympy=str(raw.get("sympy") or "").strip(),
            latex=str(raw.get("latex") or "").strip(),
            description=str(raw.get("description") or "").strip(),
            tags=[str(tag).strip() for tag in (raw.get("tags") or []) if str(tag).strip()],
            created_at=str(raw.get("created_at") or utc_now_iso()),
            updated_at=str(raw.get("updated_at") or utc_now_iso()),
        )

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Field 'name' is required.")
        if not self.sympy:
            raise ValueError("Field 'sympy' is required.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sympy": self.sympy,
            "latex": self.latex,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
