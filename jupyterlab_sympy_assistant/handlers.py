from __future__ import annotations

import json
import inspect
from http import HTTPStatus

import tornado
from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join

from .latex_parser import convert_latex_to_bundle
from .store import EquationLibraryStore


class BaseEquationHandler(APIHandler):
    async def prepare(self) -> None:
        maybe_awaitable = super().prepare()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
        self.log.debug(
            "SymPy assistant request: method=%s path=%s",
            self.request.method,
            self.request.path,
        )

    @property
    def store(self) -> EquationLibraryStore:
        store = self.settings.get("equation_store")
        if not isinstance(store, EquationLibraryStore):
            store = EquationLibraryStore()
            self.settings["equation_store"] = store
        return store

    def write_json(self, payload: dict) -> None:
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(payload))

    def write_error_message(self, status: HTTPStatus, message: str) -> None:
        self.set_status(status)
        self.write_json({"error": message})

    def parse_json_body(self) -> dict:
        try:
            return self.get_json_body() or {}
        except Exception as err:
            self.log.warning(
                "Invalid JSON body for %s %s: %s",
                self.request.method,
                self.request.path,
                err,
            )
            self.write_error_message(
                HTTPStatus.BAD_REQUEST,
                "Request body must be valid JSON with Content-Type: application/json.",
            )
            return {}


class EquationsHandler(BaseEquationHandler):
    @tornado.web.authenticated
    def get(self) -> None:
        equations = self.store.list_equations()
        self.log.info(
            "Equation list requested: count=%s store=%s",
            len(equations),
            self.store.path,
        )
        self.write_json({"equations": equations})

    @tornado.web.authenticated
    def post(self) -> None:
        body = self.parse_json_body()
        if self._finished:
            return
        self.log.info(
            "Equation create requested: name=%r store=%s",
            body.get("name"),
            self.store.path,
        )
        try:
            created = self.store.create_equation(body)
        except ValueError as err:
            self.write_error_message(HTTPStatus.BAD_REQUEST, str(err))
            return
        self.log.info(
            "Equation created: id=%s name=%r store=%s",
            created.get("id"),
            created.get("name"),
            self.store.path,
        )
        self.set_status(HTTPStatus.CREATED)
        self.write_json({"equation": created})


class EquationByIdHandler(BaseEquationHandler):
    @tornado.web.authenticated
    def put(self, equation_id: str) -> None:
        body = self.parse_json_body()
        if self._finished:
            return
        self.log.info(
            "Equation update requested: id=%s store=%s",
            equation_id,
            self.store.path,
        )
        try:
            updated = self.store.update_equation(equation_id, body)
        except ValueError as err:
            self.write_error_message(HTTPStatus.BAD_REQUEST, str(err))
            return
        except KeyError as err:
            self.write_error_message(HTTPStatus.NOT_FOUND, str(err))
            return

        self.log.info(
            "Equation updated: id=%s name=%r store=%s",
            updated.get("id"),
            updated.get("name"),
            self.store.path,
        )
        self.write_json({"equation": updated})

    @tornado.web.authenticated
    def delete(self, equation_id: str) -> None:
        self.log.info(
            "Equation delete requested: id=%s store=%s",
            equation_id,
            self.store.path,
        )
        try:
            self.store.delete_equation(equation_id)
        except KeyError as err:
            self.write_error_message(HTTPStatus.NOT_FOUND, str(err))
            return
        self.log.info("Equation deleted: id=%s store=%s", equation_id, self.store.path)
        self.set_status(HTTPStatus.NO_CONTENT)
        self.finish()


class LatexConvertHandler(BaseEquationHandler):
    @tornado.web.authenticated
    def post(self) -> None:
        body = self.parse_json_body()
        if self._finished:
            return
        latex = str(body.get("latex") or "")
        try:
            payload = convert_latex_to_bundle(latex)
        except ValueError as err:
            self.write_error_message(HTTPStatus.BAD_REQUEST, str(err))
            return
        except RuntimeError as err:
            self.write_error_message(HTTPStatus.SERVICE_UNAVAILABLE, str(err))
            return
        except Exception as err:
            self.log.exception("LaTeX conversion failed")
            self.write_error_message(HTTPStatus.BAD_REQUEST, f"Failed to parse LaTeX: {err}")
            return

        self.write_json(payload)


def setup_route_handlers(web_app) -> None:
    host_pattern = ".*$"
    base_url = web_app.settings["base_url"]
    api_root = url_path_join(base_url, "api", "jupyterlab-sympy-assistant", "equations")

    convert_route = url_path_join(base_url, "api", "jupyterlab-sympy-assistant", "convert-latex")

    handlers = [
        (api_root, EquationsHandler),
        (url_path_join(api_root, r"([^/]+)"), EquationByIdHandler),
        (convert_route, LatexConvertHandler),
    ]

    web_app.add_handlers(host_pattern, handlers)
