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


async def test_convert_latex_endpoint(jp_fetch, monkeypatch):
    from jupyterlab_sympy_assistant import handlers

    monkeypatch.setattr(
        handlers,
        "convert_latex_to_bundle",
        lambda latex: {
            "sympy": "spp.Eq(rho, m/V)\nspp.Eq(m/V, 1/v)",
            "symbols": ["V", "m", "rho", "v"],
            "symbols_line": "V, m, rho, v = spp.symbols('V m rho v')",
            "code": "V, m, rho, v = spp.symbols('V m rho v')\nspp.Eq(rho, m/V)\nspp.Eq(m/V, 1/v)",
        },
    )

    response = await jp_fetch(
        "api",
        "jupyterlab-sympy-assistant",
        "convert-latex",
        method="POST",
        body=json.dumps({"latex": r"\rho = \frac{m}{V} = \frac{1}{v}"}),
    )
    assert response.code == 200
    payload = json.loads(response.body)
    assert payload["sympy"] == "spp.Eq(rho, m/V)\nspp.Eq(m/V, 1/v)"
    assert payload["symbols"] == ["V", "m", "rho", "v"]
