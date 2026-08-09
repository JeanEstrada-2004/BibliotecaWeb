from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from project_validation import BRAND_KEY_PATTERN, SLUG_PATTERN, project_root_from_tools, validate_project
from project_stats import write_stats


ARTIFACT_TYPES = {"presentation", "page", "mockup"}
ARTIFACT_STATUSES = {"draft", "published", "archived"}
PRESENTATION_TEMPLATES = {"blank", "academic", "visual"}


class CreationError(RuntimeError):
    """Error seguro y legible producido durante la creación de un artefacto."""


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_type: str
    area_id: str
    collection_id: str
    slug: str
    title: str
    summary: str
    artifact_id: str | None = None
    status: str = "draft"
    published_at: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    featured: bool = False
    template: str = "blank"
    brand: str | None = None
    brand_override: bool = False
    brand_data: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CreationResult:
    artifact_id: str
    target: Path
    dry_run: bool
    checked_files: int


@dataclass(frozen=True)
class PreparedArtifact:
    catalog: dict[str, object]
    entry: dict[str, object]
    target: Path
    collection_label: str


def _read_catalog(root: Path) -> dict[str, object]:
    path = root / "data" / "catalog.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CreationError(f"No se pudo leer data/catalog.json: {error}") from error
    if not isinstance(value, dict):
        raise CreationError("data/catalog.json debe contener un objeto JSON.")
    return value


def _require_slug(value: str, field_name: str) -> None:
    if not SLUG_PATTERN.fullmatch(value):
        raise CreationError(f"{field_name} debe usar minúsculas ASCII, números y guiones.")


def _require_text(value: str, field_name: str, maximum: int | None = None) -> str:
    normalized = value.strip()
    if not normalized:
        raise CreationError(f"{field_name} debe contener texto.")
    if maximum is not None and len(normalized) > maximum:
        raise CreationError(f"{field_name} no puede superar {maximum} caracteres.")
    return normalized


def _require_iso_date(value: str, field_name: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise CreationError(f"{field_name} debe usar YYYY-MM-DD.")
    try:
        dt.date.fromisoformat(value)
    except ValueError as error:
        raise CreationError(f"{field_name} no contiene una fecha válida.") from error


def _deduplicate_tags(tags: tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = _require_text(raw_tag, "Cada tag")
        if tag not in seen:
            result.append(tag)
            seen.add(tag)
    return result


def _format_validation_errors(prefix: str, issues: list[object]) -> CreationError:
    details = "\n".join(
        f"- [{issue.code}] {issue.location}: {issue.message}"
        for issue in issues
    )
    return CreationError(f"{prefix}\n{details}")


def _prepare(root: Path, spec: ArtifactSpec) -> PreparedArtifact:
    initial = validate_project(root)
    if initial.errors:
        raise _format_validation_errors("El proyecto ya contiene errores; corrígelos antes de crear:", initial.errors)

    artifact_type = spec.artifact_type.strip()
    if artifact_type not in ARTIFACT_TYPES:
        raise CreationError("type debe ser presentation, page o mockup.")
    if spec.status not in ARTIFACT_STATUSES:
        raise CreationError("status debe ser draft, published o archived.")
    if spec.template not in PRESENTATION_TEMPLATES:
        raise CreationError("template debe ser blank, academic o visual.")
    if artifact_type != "presentation" and (spec.brand_override or spec.brand_data):
        raise CreationError("brand y brand-data solo se aplican a presentaciones.")

    _require_slug(spec.area_id, "area")
    _require_slug(spec.collection_id, "collection")
    _require_slug(spec.slug, "slug")
    artifact_id = spec.artifact_id or f"{spec.area_id}-{spec.collection_id}-{spec.slug}"
    _require_slug(artifact_id, "id")
    title = _require_text(spec.title, "title")
    summary = _require_text(spec.summary, "summary", maximum=320)
    tags = _deduplicate_tags(spec.tags)

    published_at = spec.published_at
    if spec.status == "published" and published_at is None:
        published_at = dt.date.today().isoformat()
    if published_at is not None:
        _require_iso_date(published_at, "published-at")

    catalog = _read_catalog(root)
    areas = catalog.get("areas", [])
    collections = catalog.get("collections", [])
    types = catalog.get("types", [])
    artifacts = catalog.get("artifacts", [])
    if not all(isinstance(items, list) for items in (areas, collections, types, artifacts)):
        raise CreationError("El catálogo no contiene los arreglos base esperados.")

    if not any(isinstance(area, dict) and area.get("id") == spec.area_id for area in areas):
        raise CreationError(f"El área '{spec.area_id}' no existe en el catálogo.")
    matching_collection = next(
        (
            collection
            for collection in collections
            if isinstance(collection, dict)
            and collection.get("areaId") == spec.area_id
            and collection.get("id") == spec.collection_id
        ),
        None,
    )
    if matching_collection is None:
        raise CreationError(
            f"La colección '{spec.collection_id}' no existe dentro de '{spec.area_id}'."
        )
    if not any(isinstance(item, dict) and item.get("id") == artifact_type for item in types):
        raise CreationError(f"El tipo '{artifact_type}' no existe en el catálogo.")
    if any(isinstance(item, dict) and item.get("id") == artifact_id for item in artifacts):
        raise CreationError(f"El ID '{artifact_id}' ya está registrado.")
    if any(
        isinstance(item, dict)
        and item.get("areaId") == spec.area_id
        and item.get("collectionId") == spec.collection_id
        and item.get("slug") == spec.slug
        for item in artifacts
    ):
        raise CreationError("El slug ya está registrado dentro de esa colección.")

    target = root / "artefactos" / spec.area_id / spec.collection_id / spec.slug
    if target.exists():
        raise CreationError(f"La ruta de destino ya existe: {target}")

    if artifact_type == "presentation":
        template_dir = root / "templates" / "presentation" / "v1" / spec.template
        if not template_dir.is_dir():
            raise CreationError(f"No existe el template de presentación '{spec.template}'.")
        if spec.brand_override and spec.brand is not None:
            _require_slug(spec.brand, "brand")
            if not (root / "brands" / spec.brand).is_dir():
                raise CreationError(f"No existe el brand '{spec.brand}'.")
        for key, value in spec.brand_data.items():
            if not BRAND_KEY_PATTERN.fullmatch(key):
                raise CreationError(f"La clave de brand-data '{key}' no es válida.")
            _require_text(value, f"brand-data {key}")

    entry: dict[str, object] = {
        "id": artifact_id,
        "title": title,
        "slug": spec.slug,
        "areaId": spec.area_id,
        "collectionId": spec.collection_id,
        "type": artifact_type,
        "summary": summary,
        "status": spec.status,
        "tags": tags,
    }
    if published_at is not None:
        entry["publishedAt"] = published_at
    if spec.featured:
        entry["featured"] = True

    clean_catalog = {key: value for key, value in catalog.items() if not key.startswith("_")}
    clean_artifacts = clean_catalog.get("artifacts")
    if not isinstance(clean_artifacts, list):
        raise CreationError("data/catalog.json.artifacts debe ser un arreglo.")
    clean_artifacts.append(entry)
    return PreparedArtifact(
        catalog=clean_catalog,
        entry=entry,
        target=target,
        collection_label=str(matching_collection.get("label") or spec.collection_id),
    )


def _replace_first(
    pattern: str,
    replacement: str | Callable[[re.Match[str]], str],
    source: str,
) -> str:
    safe_replacement = replacement if callable(replacement) else lambda _match: replacement
    updated, count = re.subn(pattern, safe_replacement, source, count=1, flags=re.IGNORECASE | re.DOTALL)
    if count != 1:
        raise CreationError(f"El template no contiene el patrón requerido: {pattern}")
    return updated


def _write_presentation(root: Path, stage: Path, spec: ArtifactSpec, prepared: PreparedArtifact) -> None:
    template_dir = root / "templates" / "presentation" / "v1" / spec.template
    shutil.copytree(template_dir, stage)
    template_note = stage / "TEMPLATE.md"
    if template_note.exists():
        template_note.unlink()

    config_path = stage / "presentation.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["presentationId"] = prepared.entry["id"]
    if spec.brand_override:
        config["brand"] = spec.brand
        if spec.brand is None:
            config.pop("brandData", None)
    if spec.brand_data:
        if config.get("brand") is None:
            raise CreationError("brand-data requiere un brand activo.")
        current_data = config.get("brandData")
        if not isinstance(current_data, dict):
            current_data = {}
        current_data.update(spec.brand_data)
        config["brandData"] = current_data
    if config.get("brand") == "usmp":
        brand_data = config.setdefault("brandData", {})
        if isinstance(brand_data, dict) and brand_data.get("course") == "Nombre del curso":
            brand_data["course"] = prepared.collection_label
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    title = html.escape(str(prepared.entry["title"]))
    summary = html.escape(str(prepared.entry["summary"]), quote=True)
    collection = html.escape(prepared.collection_label)
    index_path = stage / "index.html"
    source = index_path.read_text(encoding="utf-8")
    source = _replace_first(r"<title>.*?</title>", f"<title>{title}</title>", source)
    source = _replace_first(
        r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
        f'<meta name="description" content="{summary}">',
        source,
    )
    source = _replace_first(r'aria-label="[^"]*"', f'aria-label="{title}"', source)
    source = _replace_first(
        r"(<h1[^>]*>).*?</h1>",
        lambda match: f"{match.group(1)}{title}</h1>",
        source,
    )
    source = re.sub(
        r'<p\s+class="kicker">.*?</p>',
        lambda _match: f'<p class="kicker">{collection}</p>',
        source,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    index_path.write_text(source, encoding="utf-8")


def _base_html(spec: ArtifactSpec, prepared: PreparedArtifact, kind_label: str) -> str:
    title = html.escape(str(prepared.entry["title"]))
    summary = html.escape(str(prepared.entry["summary"]))
    description = html.escape(str(prepared.entry["summary"]), quote=True)
    collection = html.escape(prepared.collection_label)
    return f'''<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="{description}">
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <header class="site-header">
      <a href="../../../../" aria-label="Volver a BibliotecaWeb">← BibliotecaWeb</a>
      <span>{html.escape(kind_label)}</span>
    </header>
    <main>
      <section class="hero" aria-labelledby="artifact-title">
        <p class="eyebrow">{collection}</p>
        <h1 id="artifact-title">{title}</h1>
        <p class="summary">{summary}</p>
      </section>
      <section class="workspace" aria-labelledby="workspace-title">
        <div>
          <p class="eyebrow">Punto de partida</p>
          <h2 id="workspace-title">Contenido listo para personalizar</h2>
          <p>Reemplaza este bloque por el contenido y las interacciones propias del artefacto.</p>
        </div>
        <button type="button" data-action="confirm">Probar interacción</button>
        <p class="feedback" data-feedback aria-live="polite"></p>
      </section>
    </main>
    <script src="script.js"></script>
  </body>
</html>
'''


def _base_css(artifact_type: str) -> str:
    accent = "#2563eb" if artifact_type == "page" else "#7c3aed"
    return f''':root {{
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #172033;
  background: #f4f7fb;
  --accent: {accent};
}}

* {{ box-sizing: border-box; }}

body {{
  min-height: 100vh;
  margin: 0;
  background: radial-gradient(circle at top right, #dbeafe 0, transparent 34rem), #f4f7fb;
}}

.site-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 72rem;
  margin: 0 auto;
  padding: 1.25rem clamp(1rem, 4vw, 3rem);
}}

.site-header a {{ color: var(--accent); font-weight: 750; text-decoration: none; }}

main {{
  width: min(72rem, calc(100% - 2rem));
  margin: 3rem auto;
}}

.hero, .workspace {{
  padding: clamp(1.5rem, 5vw, 4rem);
  border: 1px solid #dbe3ef;
  border-radius: 1.5rem;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 1.5rem 4rem rgba(45, 58, 90, 0.09);
}}

.workspace {{ margin-top: 1.25rem; }}
.eyebrow {{ color: var(--accent); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }}
h1 {{ max-width: 18ch; margin: .25rem 0 1rem; font-size: clamp(2.5rem, 8vw, 5.5rem); line-height: .98; }}
h2 {{ font-size: clamp(1.5rem, 4vw, 2.4rem); }}
.summary {{ max-width: 48rem; color: #536078; font-size: clamp(1.05rem, 2vw, 1.3rem); line-height: 1.65; }}
button {{
  border: 0;
  border-radius: 999px;
  padding: .85rem 1.25rem;
  color: white;
  background: var(--accent);
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}}
button:focus-visible, a:focus-visible {{ outline: .2rem solid #f59e0b; outline-offset: .2rem; }}
.feedback {{ min-height: 1.5rem; color: #536078; }}

@media (max-width: 42rem) {{
  main {{ margin-top: 1rem; }}
  .site-header {{ align-items: flex-start; gap: .75rem; }}
}}
'''


def _base_script(artifact_type: str) -> str:
    message = (
        "La página está lista para recibir tu contenido."
        if artifact_type == "page"
        else "El mockup está listo para que modeles su flujo."
    )
    return f'''const action = document.querySelector("[data-action='confirm']");
const feedback = document.querySelector("[data-feedback]");

if (action && feedback) {{
  action.addEventListener("click", () => {{
    feedback.textContent = "{message}";
  }});
}}
'''


def _write_generic(stage: Path, spec: ArtifactSpec, prepared: PreparedArtifact) -> None:
    stage.mkdir(parents=True)
    label = "Página" if spec.artifact_type == "page" else "Mockup"
    (stage / "index.html").write_text(_base_html(spec, prepared, label), encoding="utf-8")
    (stage / "styles.css").write_text(_base_css(spec.artifact_type), encoding="utf-8")
    (stage / "script.js").write_text(_base_script(spec.artifact_type), encoding="utf-8")


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _commit(root: Path, spec: ArtifactSpec, prepared: PreparedArtifact) -> CreationResult:
    target = prepared.target
    collection_dir = target.parent
    collection_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    stage = collection_dir / f".tmp-create-{token}"
    catalog_path = root / "data" / "catalog.json"
    stats_path = root / "data" / "stats.json"
    catalog_temp = catalog_path.parent / f".catalog-{token}.tmp"
    rollback_temp = catalog_path.parent / f".catalog-rollback-{token}.tmp"
    original_catalog = catalog_path.read_bytes()
    original_stats = stats_path.read_bytes() if stats_path.is_file() else None
    target_created = False

    try:
        if spec.artifact_type == "presentation":
            _write_presentation(root, stage, spec, prepared)
        else:
            _write_generic(stage, spec, prepared)
        catalog_temp.write_text(
            json.dumps(prepared.catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        stage.rename(target)
        target_created = True
        os.replace(catalog_temp, catalog_path)
        write_stats(root)
        validation = validate_project(root)
        if validation.errors:
            raise _format_validation_errors("La creación no superó la validación final:", validation.errors)
        return CreationResult(
            artifact_id=str(prepared.entry["id"]),
            target=target,
            dry_run=False,
            checked_files=validation.checked_files,
        )
    except Exception:
        if catalog_path.read_bytes() != original_catalog:
            rollback_temp.write_bytes(original_catalog)
            os.replace(rollback_temp, catalog_path)
        if original_stats is None:
            if stats_path.is_file() and stats_path.parent.resolve() == catalog_path.parent.resolve():
                stats_path.unlink()
        elif not stats_path.is_file() or stats_path.read_bytes() != original_stats:
            stats_rollback = stats_path.parent / f".stats-rollback-{token}.tmp"
            stats_rollback.write_bytes(original_stats)
            os.replace(stats_rollback, stats_path)
        artifacts_root = root / "artefactos"
        if target_created and target.is_dir() and _is_inside(target, artifacts_root):
            shutil.rmtree(target)
        raise
    finally:
        if stage.is_dir() and _is_inside(stage, root / "artefactos"):
            shutil.rmtree(stage)
        for temporary in (catalog_temp, rollback_temp):
            if temporary.is_file() and temporary.parent.resolve() == catalog_path.parent.resolve():
                temporary.unlink()


def _copy_for_simulation(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "__pycache__"}}

    shutil.copytree(source, destination, ignore=ignore)


def create_artifact(root: Path | str, spec: ArtifactSpec, dry_run: bool = False) -> CreationResult:
    selected_root = Path(root).resolve()
    prepared = _prepare(selected_root, spec)
    if not dry_run:
        return _commit(selected_root, spec, prepared)

    with tempfile.TemporaryDirectory(prefix="biblioteca-simulation-") as temporary:
        simulated_root = Path(temporary) / "BibliotecaWeb"
        _copy_for_simulation(selected_root, simulated_root)
        simulated_prepared = _prepare(simulated_root, spec)
        simulated_result = _commit(simulated_root, spec, simulated_prepared)
        return CreationResult(
            artifact_id=simulated_result.artifact_id,
            target=prepared.target,
            dry_run=True,
            checked_files=simulated_result.checked_files,
        )


def _parse_brand_data(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("brand-data debe usar CLAVE=VALOR.")
        key, content = value.split("=", 1)
        key = key.strip()
        if key in result:
            raise argparse.ArgumentTypeError(f"La clave de brand-data '{key}' está repetida.")
        result[key] = content.strip()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea y registra un artefacto de BibliotecaWeb de forma transaccional.",
    )
    parser.add_argument("--root", type=Path, default=project_root_from_tools(), help="Raíz de BibliotecaWeb.")
    parser.add_argument("--type", required=True, choices=sorted(ARTIFACT_TYPES), dest="artifact_type")
    parser.add_argument("--area", required=True, dest="area_id")
    parser.add_argument("--collection", required=True, dest="collection_id")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--id", dest="artifact_id")
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--status", choices=sorted(ARTIFACT_STATUSES), default="draft")
    parser.add_argument("--published-at")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--featured", action="store_true")
    parser.add_argument("--template", choices=sorted(PRESENTATION_TEMPLATES), default="blank")
    parser.add_argument("--brand", help="Slug del brand; usa 'none' para desactivarlo.")
    parser.add_argument("--brand-data", action="append", default=[], metavar="CLAVE=VALOR")
    parser.add_argument("--dry-run", action="store_true", help="Valida sobre una copia temporal sin escribir el proyecto.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        brand_data = _parse_brand_data(args.brand_data)
        brand_override = args.brand is not None
        brand = None if args.brand == "none" else args.brand
        spec = ArtifactSpec(
            artifact_type=args.artifact_type,
            area_id=args.area_id,
            collection_id=args.collection_id,
            slug=args.slug,
            title=args.title,
            summary=args.summary,
            artifact_id=args.artifact_id,
            status=args.status,
            published_at=args.published_at,
            tags=tuple(args.tag),
            featured=args.featured,
            template=args.template,
            brand=brand,
            brand_override=brand_override,
            brand_data=brand_data,
        )
        result = create_artifact(args.root, spec, dry_run=args.dry_run)
    except (CreationError, argparse.ArgumentTypeError) as error:
        parser.exit(2, f"ERROR: {error}\n")

    action = "Simulación correcta" if result.dry_run else "Artefacto creado"
    print(f"{action}: {result.artifact_id}")
    print(f"Ruta: {result.target}")
    print(f"Validación: 0 errores; {result.checked_files} archivos revisados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
