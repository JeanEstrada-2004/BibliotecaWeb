from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_validation import project_root_from_tools, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Valida la estructura completa de BibliotecaWeb sin dependencias externas.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=project_root_from_tools(),
        help="Raíz del proyecto. Por defecto se deriva desde tools/.",
    )
    parser.add_argument("--strict", action="store_true", help="Trata las advertencias como fallo.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Devuelve un reporte JSON.")
    parser.add_argument("--quiet", action="store_true", help="Muestra únicamente el resumen.")
    return parser


def print_text(result, quiet: bool) -> None:
    if not quiet:
        for issue in result.issues:
            label = "ERROR" if issue.severity == "error" else "AVISO"
            print(f"{label} [{issue.code}] {issue.location}: {issue.message}")
    print(
        "Resumen: "
        f"{len(result.errors)} errores, "
        f"{len(result.warnings)} avisos, "
        f"{result.artifact_count} artefactos, "
        f"{result.presentation_count} presentaciones, "
        f"{result.template_count} templates, "
        f"{result.brand_count} brands, "
        f"{result.checked_files} archivos revisados."
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_project(args.root)
    if args.as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text(result, args.quiet)
    return 1 if result.errors or (args.strict and result.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
