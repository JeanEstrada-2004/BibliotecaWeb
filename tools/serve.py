from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from project_validation import project_root_from_tools, validate_project


class LocalHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[HTTP] {self.address_string()} - {format % args}")


def first_presentation_path(root: Path) -> str | None:
    try:
        catalog = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    presentations = [
        artifact
        for artifact in catalog.get("artifacts", [])
        if isinstance(artifact, dict) and artifact.get("type") == "presentation"
    ]
    presentations.sort(key=lambda artifact: artifact.get("publishedAt", ""), reverse=True)
    if not presentations:
        return None
    artifact = presentations[0]
    return "/".join(
        [
            "artefactos",
            str(artifact.get("areaId", "")),
            str(artifact.get("collectionId", "")),
            str(artifact.get("slug", "")),
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Abre BibliotecaWeb mediante un servidor HTTP local sin dependencias.",
    )
    parser.add_argument("--root", type=Path, default=project_root_from_tools(), help="Raíz de BibliotecaWeb.")
    parser.add_argument("--port", type=int, default=8000, help="Puerto local. Por defecto: 8000.")
    parser.add_argument("--no-open", action="store_true", help="No abre automáticamente el navegador.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not 1 <= args.port <= 65535:
        parser.error("port debe estar entre 1 y 65535.")

    validation = validate_project(root)
    if validation.errors:
        print("No se puede iniciar porque el proyecto contiene errores:")
        for issue in validation.errors:
            print(f"- [{issue.code}] {issue.location}: {issue.message}")
        return 1

    handler = partial(LocalHandler, directory=str(root))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        print(f"No se pudo iniciar el servidor local: {error}")
        return 2

    base_url = f"http://127.0.0.1:{args.port}/"
    presentation_path = first_presentation_path(root)
    print(f"BibliotecaWeb: {base_url}")
    print(f"Estado: {base_url}estado/")
    if presentation_path:
        print(f"Presentación de prueba: {base_url}{presentation_path}")
    else:
        print("No hay presentaciones registradas todavía.")
    print("Presiona Ctrl+C para cerrar.")

    if not args.no_open:
        opener = threading.Timer(0.25, lambda: webbrowser.open(base_url, new=2))
        opener.daemon = True
        opener.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor local cerrado.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
