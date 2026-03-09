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
