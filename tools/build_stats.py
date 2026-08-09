from __future__ import annotations

import argparse
import json
from pathlib import Path

from project_stats import GENERATED_STATS_PATH, StatsError, calculate_stats, write_stats
from project_validation import project_root_from_tools, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calcula la huella web publicable y actualiza data/stats.json.",
    )
    parser.add_argument("--root", type=Path, default=project_root_from_tools(), help="Raíz de BibliotecaWeb.")
    parser.add_argument("--check", action="store_true", help="Comprueba que stats.json esté actualizado sin escribir.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Muestra el resultado calculado como JSON.")
    return parser


def _stored_stats(root: Path) -> dict[str, object]:
    path = root / GENERATED_STATS_PATH
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StatsError(f"No se pudo leer {GENERATED_STATS_PATH}: {error}") from error
    if not isinstance(value, dict):
        raise StatsError(f"{GENERATED_STATS_PATH} debe contener un objeto JSON.")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.check:
            stored = _stored_stats(root)
            current = calculate_stats(root, generated_at=str(stored.get("generatedAt") or ""))
            if current != stored:
                parser.exit(1, "ERROR: data/stats.json no corresponde al estado actual del proyecto.\n")
            stats = current
        else:
            stats = write_stats(root)

        validation = validate_project(root)
        non_stats_errors = [
            issue
            for issue in validation.errors
            if not issue.code.startswith(("stats-", "policy-"))
        ]
        if non_stats_errors:
            details = "\n".join(
                f"- [{issue.code}] {issue.location}: {issue.message}" for issue in non_stats_errors
            )
            parser.exit(1, f"ERROR: el proyecto contiene errores ajenos a estadísticas:\n{details}\n")
    except StatsError as error:
        parser.exit(2, f"ERROR: {error}\n")

    if args.as_json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        action = "Estadísticas vigentes" if args.check else "Estadísticas actualizadas"
        print(
            f"{action}: {stats['summary']['totalBytes']} bytes, "
            f"{stats['summary']['artifactCount']} artefactos, "
            f"estado {stats['policy']['status']['label']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
