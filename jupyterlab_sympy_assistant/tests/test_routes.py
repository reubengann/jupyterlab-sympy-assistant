import json

import pytest
from tornado.httpclient import HTTPClientError


async def test_equation_crud(jp_fetch):
    create_payload = {
        "name": "Quadratic Formula",
        "sympy": "x = (-b + sqrt(b**2 - 4*a*c)) / (2*a)",
        "latex": r"x=\frac{-b+\sqrt{b^2-4ac}}{2a}",
        "description": "Positive branch",
        "tags": ["algebra", "quadratic"],
    }

    # Create
    create_response = await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "equations",
        method="POST",
        body=json.dumps(create_payload),
    )
    assert create_response.code == 201
    created = json.loads(create_response.body)["equation"]
    assert created["name"] == create_payload["name"]
    equation_id = created["id"]

    # List
    list_response = await jp_fetch("api", "jupyterlab-sympy-assistant", "equations")
    assert list_response.code == 200
    listed = json.loads(list_response.body)["equations"]
    assert len(listed) == 1
    assert listed[0]["id"] == equation_id

    # Update
    update_response = await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "equations",
        equation_id,
        method="PUT",
        body=json.dumps({"name": "Quadratic Formula Updated"}),
    )
    assert update_response.code == 200
    updated = json.loads(update_response.body)["equation"]
    assert updated["name"] == "Quadratic Formula Updated"

    # Delete
    delete_response = await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "equations",
        equation_id,
        method="DELETE",
    )
    assert delete_response.code == 204

    list_after_delete = await jp_fetch("api", "jupyterlab-sympy-assistant", "equations")
    assert list_after_delete.code == 200
    payload_after_delete = json.loads(list_after_delete.body)
    assert payload_after_delete["equations"] == []


async def test_validation_error(jp_fetch):
    with pytest.raises(HTTPClientError) as err:
        await jp_fetch(
            "api",
            "jupyterlab-sympy-assistant",
            "equations",
            method="POST",
            body=json.dumps({"name": "", "sympy": ""}),
        )
    assert err.value.code == 400


async def test_library_export_and_import(jp_fetch):
    await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "equations",
        method="POST",
        body=json.dumps({"name": "Original", "sympy": "x"}),
    )
    export_response = await jp_fetch(
        "api", "jupyterlab-sympy-assistant", "library"
    )
    library = json.loads(export_response.body)
    assert library["schema_version"] == 1
    assert len(library["equations"]) == 1

    library["equations"][0]["name"] = "Updated"
    library["equations"].append(
        {
            "id": "imported-id",
            "name": "Imported",
            "sympy": "y",
            "latex": "",
            "description": "",
            "tags": [],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )
    import_response = await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "library",
        method="PUT",
        body=json.dumps(library),
    )
    result = json.loads(import_response.body)
    assert result == {"imported": 2, "added": 1, "updated": 1}

    list_response = await jp_fetch("api", "jupyterlab-sympy-assistant", "equations")
    equations = json.loads(list_response.body)["equations"]
    assert [equation["name"] for equation in equations] == ["Updated", "Imported"]
