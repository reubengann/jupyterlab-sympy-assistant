from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from jupyter_core.paths import jupyter_data_dir

from .models import EquationRecord, utc_now_iso

SCHEMA_VERSION = 1


class EquationLibraryStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = base_dir or Path(jupyter_data_dir()) / "jupyterlab-sympy-assistant"
        self._path = root / "equation-library.json"
        self._lock = Lock()

    @property
    def path(self) -> Path:
        return self._path

    def list_equations(self) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._load_payload()
            return payload["equations"]

    def create_equation(self, raw: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = self._load_payload()
            record = EquationRecord.from_dict(raw)
            record.validate()

            if any(existing["id"] == record.id for existing in payload["equations"]):
                raise ValueError(f"Equation with id '{record.id}' already exists.")

            payload["equations"].append(record.to_dict())
            self._write_payload(payload)
            return record.to_dict()

    def update_equation(self, equation_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            payload = self._load_payload()
            for index, existing in enumerate(payload["equations"]):
                if existing["id"] != equation_id:
                    continue

                merged = {
                    **existing,
                    **raw,
                    "id": equation_id,
                    "created_at": existing.get("created_at", utc_now_iso()),
                    "updated_at": utc_now_iso(),
                }
                record = EquationRecord.from_dict(merged)
                record.validate()
                payload["equations"][index] = record.to_dict()
                self._write_payload(payload)
                return record.to_dict()

            raise KeyError(f"Equation '{equation_id}' not found.")

    def delete_equation(self, equation_id: str) -> None:
        with self._lock:
            payload = self._load_payload()
            before = len(payload["equations"])
            payload["equations"] = [eq for eq in payload["equations"] if eq["id"] != equation_id]
            if len(payload["equations"]) == before:
                raise KeyError(f"Equation '{equation_id}' not found.")
            self._write_payload(payload)

    def _load_payload(self) -> dict[str, Any]:
        if not self._path.exists():
            payload = {"schema_version": SCHEMA_VERSION, "equations": []}
            self._write_payload(payload)
            return payload

        with self._path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported equation library schema version.")
        equations = payload.get("equations", [])
        if not isinstance(equations, list):
            raise ValueError("Invalid equation library format.")
        payload["equations"] = equations
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
        temp_path.replace(self._path)
