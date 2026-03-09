import pytest

pytest_plugins = ("pytest_jupyter.jupyter_server", )


@pytest.fixture
def jp_server_config(jp_server_config, tmp_path, monkeypatch):
    monkeypatch.setenv("JUPYTER_DATA_DIR", str(tmp_path / "jupyter-data"))
    return {"ServerApp": {"jpserver_extensions": {"jupyterlab_sympy_assistant": True}}}
