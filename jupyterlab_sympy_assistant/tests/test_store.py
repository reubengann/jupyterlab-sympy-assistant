from pathlib import Path

import pytest

from jupyterlab_sympy_assistant.store import EquationLibraryStore


def test_store_create_update_delete(tmp_path: Path):
    store = EquationLibraryStore(base_dir=tmp_path)

    created = store.create_equation(
        {
            "name": "Binomial",
            "sympy": "(a + b)**2",
            "latex": r"(a+b)^2",
            "tags": ["algebra"],
        }
    )
    assert created["name"] == "Binomial"
    listed = store.list_equations()
    assert len(listed) == 1

    updated = store.update_equation(created["id"], {"description": "Basic identity"})
    assert updated["description"] == "Basic identity"

    store.delete_equation(created["id"])
    assert store.list_equations() == []


def test_store_validates_required_fields(tmp_path: Path):
    store = EquationLibraryStore(base_dir=tmp_path)

    with pytest.raises(ValueError):
        store.create_equation({"name": "", "sympy": ""})


def test_store_exports_and_merges_import(tmp_path: Path):
    store = EquationLibraryStore(base_dir=tmp_path)
    existing = store.create_equation({"name": "Original", "sympy": "x"})
    library = store.export_library()
    library["equations"][0]["name"] = "Updated"
    library["equations"].append(
        {
            "id": "imported-id",
            "name": "Imported",
            "sympy": "y",
            "latex": "y",
            "description": "",
            "tags": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )

    result = store.import_library(library)

    assert result == {"imported": 2, "added": 1, "updated": 1}
    equations = store.list_equations()
    assert [equation["id"] for equation in equations] == [existing["id"], "imported-id"]
    assert equations[0]["name"] == "Updated"


def test_store_rejects_invalid_import_without_changing_library(tmp_path: Path):
    store = EquationLibraryStore(base_dir=tmp_path)
    existing = store.create_equation({"name": "Original", "sympy": "x"})

    with pytest.raises(ValueError):
        store.import_library(
            {
                "schema_version": 1,
                "equations": [{"name": "Invalid", "sympy": ""}],
            }
        )

    assert store.list_equations() == [existing]
