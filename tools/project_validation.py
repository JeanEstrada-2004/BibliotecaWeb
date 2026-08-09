from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BRAND_KEY_PATTERN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TRANSITIONS = {"none", "fade", "slide", "zoom"}
CHROME_LEVELS = {"full", "minimal", "none"}
STEP_EFFECTS = {"fade", "fade-up", "scale-in", "appear", "none"}
FEATURE_KEYS = {
    "controls",
    "progress",
    "slideNumber",
    "keyboard",
    "touch",
    "fullscreen",
}
SOURCE_SUFFIXES = {".html", ".css", ".js", ".mjs"}
WARNING_FILE_BYTES = 5 * 1024 * 1024
ERROR_FILE_BYTES = 50 * 1024 * 1024
WARNING_BASE64_CHARS = 100 * 1024
SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
    "personal-data.json",
    "credentials.json",
}
SENSITIVE_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    location: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class ValidationResult:
    root: Path
    issues: list[Issue]
    artifact_count: int = 0
    presentation_count: int = 0
    template_count: int = 0
    brand_count: int = 0
    checked_files: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root),
            "ok": self.ok,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "artifacts": self.artifact_count,
                "presentations": self.presentation_count,
                "templates": self.template_count,
                "brands": self.brand_count,
                "checkedFiles": self.checked_files,
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }


class SourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.resources: list[tuple[str, str, str]] = []
        self.navigations: list[str] = []
        self.ids: list[str] = []
        self.images_without_alt: list[str] = []
        self.aria_references: list[tuple[str, str]] = []
        self.label_targets: list[str] = []
        self.headings: list[int] = []
        self.buttons_without_type = 0
        self.html_lang: str | None = None
        self.title_count = 0
        self.has_viewport = False
        self.main_count = 0
        self.h1_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        if tag == "main":
            self.main_count += 1
        if tag == "h1":
            self.h1_count += 1
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "html":
            self.html_lang = values.get("lang")
        if tag == "title":
            self.title_count += 1
        if tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = True
        if tag == "label" and values.get("for"):
            self.label_targets.append(str(values["for"]))
        if tag == "button" and not values.get("type"):
            self.buttons_without_type += 1
        for attribute in ("aria-labelledby", "aria-describedby", "aria-controls"):
            if values.get(attribute):
                self.aria_references.extend(
                    (attribute, token) for token in str(values[attribute]).split()
                )
        if tag == "img" and "alt" not in values:
            self.images_without_alt.append(values.get("src") or "(sin src)")

        if tag == "a" and values.get("href"):
            self.navigations.append(values["href"])
        if tag == "link" and values.get("href"):
            self.resources.append((tag, "href", values["href"]))
        for attribute in ("src", "poster"):
            value = values.get(attribute)
            if value:
                self.resources.append((tag, attribute, value))


class PresentationParser(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, object]] = []
        self.slides: list[dict[str, str | None]] = []
        self.steps: list[tuple[str | None, dict[str, str | None]]] = []
        self.invalid_slide_children: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        parent = self.stack[-1] if self.stack else None
        is_slides = tag == "div" and "slides" in classes
        is_slide = tag == "section" and "data-slide" in values
        parent_is_slides = bool(parent and parent.get("is_slides"))

        if parent_is_slides and not is_slide:
            self.invalid_slide_children.append(tag)
        if is_slide:
            record = {
                "slide_id": values.get("data-slide-id"),
                "html_id": values.get("id"),
                "transition": values.get("data-transition"),
                "chrome": values.get("data-brand-chrome"),
                "direct": "true" if parent_is_slides else "false",
            }
            self.slides.append(record)

        current_slide = None
        for node in reversed(self.stack):
            if node.get("slide_id"):
                current_slide = str(node["slide_id"])
                break
        if is_slide:
            current_slide = values.get("data-slide-id")

        if "data-step" in values:
            self.steps.append((current_slide, values))

        if tag not in self.VOID_TAGS:
            self.stack.append(
                {
                    "tag": tag,
                    "is_slides": is_slides,
                    "slide_id": values.get("data-slide-id") if is_slide else None,
                }
            )

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].get("tag") == tag:
                del self.stack[index:]
                return


def project_root_from_tools() -> Path:
    return Path(__file__).resolve().parent.parent


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _add(
    issues: list[Issue],
    severity: str,
    code: str,
    location: str,
    message: str,
) -> None:
    issues.append(Issue(severity, code, location, message))


def _is_nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive_integer(value: object) -> bool:
    return type(value) is int and value >= 1


def _valid_date(value: object) -> bool:
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return False
    try:
        return dt.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _load_json(path: Path, root: Path, issues: list[Issue]) -> object | None:
    location = _relative(root, path)
    if not path.is_file():
        _add(issues, "error", "json-missing", location, "El archivo requerido no existe.")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as error:
        _add(issues, "error", "encoding", location, f"El archivo no es UTF-8: {error}.")
    except json.JSONDecodeError as error:
        _add(
            issues,
            "error",
            "json-syntax",
            f"{location}:{error.lineno}:{error.colno}",
            error.msg,
        )
    return None


def _check_record_shape(
    value: object,
    required: set[str],
    allowed: set[str],
    location: str,
    issues: list[Issue],
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        _add(issues, "error", "schema-type", location, "Debe ser un objeto.")
        return None
    missing = sorted(required - value.keys())
    unexpected = sorted(value.keys() - allowed)
    for key in missing:
        _add(issues, "error", "schema-required", f"{location}.{key}", "El campo es obligatorio.")
    for key in unexpected:
        _add(issues, "error", "schema-additional", f"{location}.{key}", "El campo no está permitido.")
    return value


def _check_slug(value: object, location: str, issues: list[Issue]) -> bool:
    if not isinstance(value, str) or not SLUG_PATTERN.fullmatch(value):
        _add(
            issues,
            "error",
            "slug",
            location,
            "Debe usar ASCII en minúsculas y guiones, sin espacios ni tildes.",
        )
        return False
    return True


def _validate_catalog(root: Path, issues: list[Issue]) -> tuple[dict[str, object] | None, dict[str, str]]:
    path = root / "data" / "catalog.json"
    catalog = _load_json(path, root, issues)
    artifact_types: dict[str, str] = {}
    if not isinstance(catalog, dict):
        return None, artifact_types

    top_required = {"schemaVersion", "areas", "collections", "types", "artifacts"}
    _check_record_shape(catalog, top_required, top_required, "data/catalog.json", issues)
    if catalog.get("schemaVersion") != 1:
        _add(issues, "error", "catalog-version", "data/catalog.json.schemaVersion", "Solo se admite la versión 1.")

    arrays: dict[str, list[object]] = {}
    for key in ("areas", "collections", "types", "artifacts"):
        value = catalog.get(key)
        if not isinstance(value, list):
            _add(issues, "error", "schema-type", f"data/catalog.json.{key}", "Debe ser un arreglo.")
            arrays[key] = []
        else:
            arrays[key] = value

    area_ids: set[str] = set()
    area_orders: set[int] = set()
    area_allowed = {"id", "label", "description", "order"}
    for index, raw in enumerate(arrays["areas"]):
        location = f"data/catalog.json.areas[{index}]"
        item = _check_record_shape(raw, {"id", "label", "order"}, area_allowed, location, issues)
        if item is None:
            continue
        area_id = item.get("id")
        if _check_slug(area_id, f"{location}.id", issues):
            if area_id in area_ids:
                _add(issues, "error", "area-id-duplicate", f"{location}.id", f"El área '{area_id}' está duplicada.")
            area_ids.add(str(area_id))
        if not _is_nonempty_text(item.get("label")):
            _add(issues, "error", "schema-text", f"{location}.label", "Debe contener texto.")
        if "description" in item and not _is_nonempty_text(item.get("description")):
            _add(issues, "error", "schema-text", f"{location}.description", "Debe contener texto.")
        order = item.get("order")
        if not _is_positive_integer(order):
            _add(issues, "error", "order", f"{location}.order", "Debe ser un entero mayor o igual a 1.")
        elif order in area_orders:
            _add(issues, "warning", "area-order-duplicate", f"{location}.order", f"El orden {order} se repite.")
        else:
            area_orders.add(int(order))

    collection_keys: set[tuple[str, str]] = set()
    collection_orders: dict[str, set[int]] = {}
    collection_allowed = {"id", "areaId", "label", "shortLabel", "description", "order"}
    for index, raw in enumerate(arrays["collections"]):
        location = f"data/catalog.json.collections[{index}]"
        item = _check_record_shape(
            raw,
            {"id", "areaId", "label", "order"},
            collection_allowed,
            location,
            issues,
        )
        if item is None:
            continue
        collection_id = item.get("id")
        area_id = item.get("areaId")
        valid_id = _check_slug(collection_id, f"{location}.id", issues)
        valid_area = _check_slug(area_id, f"{location}.areaId", issues)
        if valid_area and area_id not in area_ids:
            _add(issues, "error", "collection-area", f"{location}.areaId", f"El área '{area_id}' no existe.")
        if valid_id and valid_area:
            key = (str(area_id), str(collection_id))
            if key in collection_keys:
                _add(issues, "error", "collection-id-duplicate", f"{location}.id", "La colección está duplicada dentro del área.")
            collection_keys.add(key)
        if not _is_nonempty_text(item.get("label")):
            _add(issues, "error", "schema-text", f"{location}.label", "Debe contener texto.")
        for optional in ("shortLabel", "description"):
            if optional in item and not _is_nonempty_text(item.get(optional)):
                _add(issues, "error", "schema-text", f"{location}.{optional}", "Debe contener texto.")
        order = item.get("order")
        if not _is_positive_integer(order):
            _add(issues, "error", "order", f"{location}.order", "Debe ser un entero mayor o igual a 1.")
        elif isinstance(area_id, str):
            seen = collection_orders.setdefault(area_id, set())
            if order in seen:
                _add(issues, "warning", "collection-order-duplicate", f"{location}.order", f"El orden {order} se repite en '{area_id}'.")
            seen.add(int(order))

    type_ids: set[str] = set()
    type_orders: set[int] = set()
    type_allowed = {"id", "label", "description", "order"}
    for index, raw in enumerate(arrays["types"]):
        location = f"data/catalog.json.types[{index}]"
        item = _check_record_shape(raw, {"id", "label", "order"}, type_allowed, location, issues)
        if item is None:
            continue
        type_id = item.get("id")
        if _check_slug(type_id, f"{location}.id", issues):
            if type_id in type_ids:
                _add(issues, "error", "type-id-duplicate", f"{location}.id", f"El tipo '{type_id}' está duplicado.")
            type_ids.add(str(type_id))
            artifact_types[str(type_id)] = str(item.get("label") or type_id)
        if not _is_nonempty_text(item.get("label")):
            _add(issues, "error", "schema-text", f"{location}.label", "Debe contener texto.")
        if "description" in item and not _is_nonempty_text(item.get("description")):
            _add(issues, "error", "schema-text", f"{location}.description", "Debe contener texto.")
        order = item.get("order")
        if not _is_positive_integer(order):
            _add(issues, "error", "order", f"{location}.order", "Debe ser un entero mayor o igual a 1.")
        elif order in type_orders:
            _add(issues, "warning", "type-order-duplicate", f"{location}.order", f"El orden {order} se repite.")
        else:
            type_orders.add(int(order))

    artifact_ids: set[str] = set()
    artifact_slugs: set[tuple[str, str, str]] = set()
    artifact_allowed = {
        "id",
        "title",
        "slug",
        "areaId",
        "collectionId",
        "type",
        "summary",
        "status",
        "publishedAt",
        "updatedAt",
        "tags",
        "cover",
        "featured",
        "details",
    }
    registered_directories: set[str] = set()
    artifacts_root = root / "artefactos"

    for index, raw in enumerate(arrays["artifacts"]):
        location = f"data/catalog.json.artifacts[{index}]"
        item = _check_record_shape(
            raw,
            {"id", "title", "slug", "areaId", "collectionId", "type", "summary", "status", "tags"},
            artifact_allowed,
            location,
            issues,
        )
        if item is None:
            continue
        artifact_id = item.get("id")
        slug_value = item.get("slug")
        area_id = item.get("areaId")
        collection_id = item.get("collectionId")
        type_id = item.get("type")
        valid_artifact_id = _check_slug(artifact_id, f"{location}.id", issues)
        valid_slug = _check_slug(slug_value, f"{location}.slug", issues)
        valid_area = _check_slug(area_id, f"{location}.areaId", issues)
        valid_collection = _check_slug(collection_id, f"{location}.collectionId", issues)
        valid_type = _check_slug(type_id, f"{location}.type", issues)

        if valid_artifact_id:
            if artifact_id in artifact_ids:
                _add(issues, "error", "artifact-id-duplicate", f"{location}.id", f"El ID '{artifact_id}' está duplicado.")
            artifact_ids.add(str(artifact_id))
        if valid_area and area_id not in area_ids:
            _add(issues, "error", "artifact-area", f"{location}.areaId", f"El área '{area_id}' no existe.")
        if valid_area and valid_collection and (str(area_id), str(collection_id)) not in collection_keys:
            _add(issues, "error", "artifact-collection", f"{location}.collectionId", "La colección no existe dentro del área.")
        if valid_type and type_id not in type_ids:
            _add(issues, "error", "artifact-type", f"{location}.type", f"El tipo '{type_id}' no existe.")
        if valid_area and valid_collection and valid_slug:
            slug_key = (str(area_id), str(collection_id), str(slug_value))
            if slug_key in artifact_slugs:
                _add(issues, "error", "artifact-slug-duplicate", f"{location}.slug", "El slug se repite dentro de la colección.")
            artifact_slugs.add(slug_key)
            canonical = f"artefactos/{area_id}/{collection_id}/{slug_value}"
            registered_directories.add(canonical)
            artifact_dir = root / canonical
            if not artifact_dir.is_dir():
                _add(issues, "error", "artifact-folder-missing", canonical, "La carpeta registrada no existe.")
            elif not (artifact_dir / "index.html").is_file():
                _add(issues, "error", "artifact-index-missing", f"{canonical}/index.html", "Todo artefacto necesita index.html.")

        if not _is_nonempty_text(item.get("title")):
            _add(issues, "error", "schema-text", f"{location}.title", "Debe contener texto.")
        summary = item.get("summary")
        if not _is_nonempty_text(summary) or len(str(summary)) > 320:
            _add(issues, "error", "artifact-summary", f"{location}.summary", "Debe contener entre 1 y 320 caracteres.")
        status = item.get("status")
        if status not in {"draft", "published", "archived"}:
            _add(issues, "error", "artifact-status", f"{location}.status", "Debe ser draft, published o archived.")
        if status == "published" and "publishedAt" not in item:
            _add(issues, "error", "published-date-required", f"{location}.publishedAt", "Un artefacto published requiere fecha.")
        for date_key in ("publishedAt", "updatedAt"):
            if date_key in item and not _valid_date(item.get(date_key)):
                _add(issues, "error", "date", f"{location}.{date_key}", "Debe usar una fecha ISO válida YYYY-MM-DD.")
        tags = item.get("tags")
        if not isinstance(tags, list) or any(not _is_nonempty_text(tag) for tag in tags):
            _add(issues, "error", "artifact-tags", f"{location}.tags", "Debe ser un arreglo de textos no vacíos.")
        elif len(tags) != len(set(tags)):
            _add(issues, "error", "artifact-tags-duplicate", f"{location}.tags", "No puede contener valores duplicados.")
        if "featured" in item and not isinstance(item.get("featured"), bool):
            _add(issues, "error", "schema-type", f"{location}.featured", "Debe ser booleano.")
        details = item.get("details")
        if details is not None:
            if not isinstance(details, dict):
                _add(issues, "error", "schema-type", f"{location}.details", "Debe ser un objeto.")
            else:
                for detail_key, detail_value in details.items():
                    if not SLUG_PATTERN.fullmatch(detail_key) or not isinstance(detail_value, dict):
                        _add(issues, "error", "artifact-details", f"{location}.details.{detail_key}", "La clave debe ser slug y su valor un objeto.")

        if "cover" in item and valid_area and valid_collection and valid_slug:
            cover = item.get("cover")
            if not isinstance(cover, str) or not cover.startswith("assets/") or ".." in Path(cover).parts:
                _add(issues, "error", "artifact-cover", f"{location}.cover", "Debe ser una ruta segura dentro de assets/.")
            else:
                cover_path = root / "artefactos" / str(area_id) / str(collection_id) / str(slug_value) / cover
                if not cover_path.is_file():
                    _add(issues, "error", "artifact-cover-missing", f"{location}.cover", f"No existe '{cover}'.")

    actual_directories: set[str] = set()
    if artifacts_root.is_dir():
        for area_dir in sorted(path for path in artifacts_root.iterdir() if path.is_dir()):
            for collection_dir in sorted(path for path in area_dir.iterdir() if path.is_dir()):
                for artifact_dir in sorted(path for path in collection_dir.iterdir() if path.is_dir()):
                    canonical = _relative(root, artifact_dir)
                    if artifact_dir.name.startswith("."):
                        _add(issues, "error", "artifact-temporary-folder", canonical, "Existe una carpeta temporal sin limpiar.")
                        continue
                    actual_directories.add(canonical)
                    if canonical not in registered_directories:
                        _add(issues, "error", "artifact-unregistered", canonical, "La carpeta no está registrada en el catálogo.")
    for canonical in sorted(registered_directories - actual_directories):
        _add(issues, "error", "artifact-folder-missing", canonical, "La carpeta registrada no existe con el casing esperado.")

    catalog["_registeredDirectories"] = registered_directories
    catalog["_artifactTypes"] = artifact_types
    return catalog, artifact_types


def _validate_presentation_config(
    config_path: Path,
    root: Path,
    issues: list[Issue],
    expected_id: str | None = None,
) -> dict[str, object] | None:
    config = _load_json(config_path, root, issues)
    location = _relative(root, config_path)
    if not isinstance(config, dict):
        return None
    allowed = {
        "contractVersion",
        "presentationId",
        "brand",
        "brandData",
        "homeHref",
        "aspectRatio",
        "chromeDefault",
        "transition",
        "features",
    }
    required = {
        "contractVersion",
        "presentationId",
        "aspectRatio",
        "chromeDefault",
        "transition",
        "features",
    }
    _check_record_shape(config, required, allowed, location, issues)
    if config.get("contractVersion") != 1:
        _add(issues, "error", "presentation-version", f"{location}.contractVersion", "Solo se admite el contrato 1.")
    presentation_id = config.get("presentationId")
    _check_slug(presentation_id, f"{location}.presentationId", issues)
    if expected_id and presentation_id != expected_id:
        _add(issues, "error", "presentation-id-mismatch", f"{location}.presentationId", f"Debe coincidir con el ID '{expected_id}' del catálogo.")
    brand = config.get("brand")
    if brand is not None:
        if _check_slug(brand, f"{location}.brand", issues):
            brand_dir = root / "brands" / str(brand)
            for filename in ("brand.css", "brand.js"):
                if not (brand_dir / filename).is_file():
                    _add(issues, "error", "brand-file-missing", _relative(root, brand_dir / filename), f"El brand declarado requiere {filename}.")
    brand_data = config.get("brandData", {})
    if not isinstance(brand_data, dict):
        _add(issues, "error", "brand-data-type", f"{location}.brandData", "Debe ser un objeto.")
    else:
        if brand is None and brand_data:
            _add(issues, "error", "brand-data-without-brand", f"{location}.brandData", "brandData requiere un brand declarado.")
        for key, value in brand_data.items():
            if not BRAND_KEY_PATTERN.fullmatch(key):
                _add(issues, "error", "brand-data-key", f"{location}.brandData.{key}", "La clave debe usar camelCase ASCII.")
            if value is not None and (not isinstance(value, str) or len(value) > 160):
                _add(issues, "error", "brand-data-value", f"{location}.brandData.{key}", "Debe ser null o texto de hasta 160 caracteres.")
    home_href = config.get("homeHref", "../../../../")
    home_location = f"{location}.homeHref"
    if (
        not isinstance(home_href, str)
        or not home_href
        or home_href.strip() != home_href
        or len(home_href) > 256
        or home_href.startswith(("/", "\\"))
        or re.match(r"^[a-z][a-z\d+.-]*:", home_href, re.IGNORECASE)
        or "?" in home_href
        or "#" in home_href
    ):
        _add(issues, "error", "presentation-home-href", home_location, "Debe ser una ruta local relativa de hasta 256 caracteres.")
    else:
        home_target = (config_path.parent / home_href).resolve()
        if not _inside(home_target, root) or not home_target.exists():
            _add(issues, "error", "presentation-home-target", home_location, "La ruta de regreso debe resolver dentro del proyecto.")
    if config.get("aspectRatio") != "16:9":
        _add(issues, "error", "presentation-aspect", f"{location}.aspectRatio", "V1 requiere 16:9.")
    if config.get("chromeDefault") not in CHROME_LEVELS:
        _add(issues, "error", "presentation-chrome", f"{location}.chromeDefault", "Debe ser full, minimal o none.")

    transition = config.get("transition")
    if not isinstance(transition, dict):
        _add(issues, "error", "schema-type", f"{location}.transition", "Debe ser un objeto.")
    else:
        _check_record_shape(transition, {"default", "durationMs"}, {"default", "durationMs"}, f"{location}.transition", issues)
        if transition.get("default") not in TRANSITIONS:
            _add(issues, "error", "presentation-transition", f"{location}.transition.default", "Transición no soportada.")
        duration = transition.get("durationMs")
        if type(duration) is not int or duration < 0 or duration > 3000:
            _add(issues, "error", "presentation-duration", f"{location}.transition.durationMs", "Debe ser un entero entre 0 y 3000.")

    features = config.get("features")
    if not isinstance(features, dict):
        _add(issues, "error", "schema-type", f"{location}.features", "Debe ser un objeto.")
    else:
        _check_record_shape(features, FEATURE_KEYS, FEATURE_KEYS, f"{location}.features", issues)
        for key in FEATURE_KEYS:
            if not isinstance(features.get(key), bool):
                _add(issues, "error", "presentation-feature", f"{location}.features.{key}", "Debe ser booleano.")
    return config


def _validate_presentation_markup(html_path: Path, root: Path, issues: list[Issue]) -> None:
    location = _relative(root, html_path)
    try:
        source = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        _add(issues, "error", "html-read", location, str(error))
        return
    parser = PresentationParser()
    parser.feed(source)
    if not parser.slides:
        _add(issues, "error", "presentation-slides", location, "La presentación necesita al menos un section[data-slide].")
        return
    if parser.invalid_slide_children:
        _add(issues, "error", "presentation-slide-child", location, "Cada hijo directo de .slides debe ser section[data-slide].")

    slide_ids: set[str] = set()
    step_ids: dict[str, set[str]] = {}
    for index, slide in enumerate(parser.slides):
        slide_location = f"{location}:slide[{index}]"
        slide_id = slide.get("slide_id")
        if not isinstance(slide_id, str) or not SLUG_PATTERN.fullmatch(slide_id):
            _add(issues, "error", "slide-id", slide_location, "data-slide-id debe ser un slug válido.")
            continue
        if slide_id in slide_ids:
            _add(issues, "error", "slide-id-duplicate", slide_location, f"El slide '{slide_id}' está duplicado.")
        slide_ids.add(slide_id)
        if slide.get("direct") != "true":
            _add(issues, "error", "slide-nested", slide_location, "V1 no permite slides anidadas.")
        if slide.get("html_id") and slide.get("html_id") != slide_id:
            _add(issues, "error", "slide-html-id", slide_location, "El id HTML debe coincidir con data-slide-id.")
        transition = slide.get("transition")
        if transition and transition not in TRANSITIONS:
            _add(issues, "error", "slide-transition", slide_location, f"La transición '{transition}' no está soportada.")
        chrome = slide.get("chrome")
        if chrome and chrome not in CHROME_LEVELS:
            _add(issues, "error", "slide-chrome", slide_location, f"El chrome '{chrome}' no está soportado.")

    for index, (slide_id, step) in enumerate(parser.steps):
        step_location = f"{location}:step[{index}]"
        if not slide_id:
            _add(issues, "error", "step-outside-slide", step_location, "El step debe vivir dentro de un slide.")
            continue
        step_id = step.get("data-step-id")
        if not isinstance(step_id, str) or not SLUG_PATTERN.fullmatch(step_id):
            _add(issues, "error", "step-id", step_location, "data-step-id debe ser un slug válido.")
        else:
            seen = step_ids.setdefault(slide_id, set())
            if step_id in seen:
                _add(issues, "error", "step-id-duplicate", step_location, f"El step '{step_id}' está duplicado en '{slide_id}'.")
            seen.add(step_id)
        effect = step.get("data-step-effect")
        if effect and effect not in STEP_EFFECTS:
            _add(issues, "error", "step-effect", step_location, f"El efecto '{effect}' no está soportado.")
        step_index = step.get("data-step-index")
        if step_index is not None and (not step_index.isdigit() or int(step_index) < 0):
            _add(issues, "error", "step-index", step_location, "data-step-index debe ser un entero no negativo.")


def _extract_references(path: Path, source: str) -> tuple[list[tuple[str, str]], SourceParser | None]:
    references: list[tuple[str, str]] = []
    parser: SourceParser | None = None
    if path.suffix == ".html":
        parser = SourceParser()
        parser.feed(source)
        references.extend(("resource", value) for _, _, value in parser.resources)
        references.extend(("navigation", value) for value in parser.navigations)
    elif path.suffix == ".css":
        pattern = re.compile(r"(?:@import\s+url\(|url\()[\"']?([^\"')]+)[\"']?\)")
        references.extend(("resource", match.group(1)) for match in pattern.finditer(source))
    elif path.suffix in {".js", ".mjs"}:
        pattern = re.compile(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']")
        references.extend(("resource", match.group(1)) for match in pattern.finditer(source))
    return references, parser


def _resolve_reference(value: str, source_path: Path) -> tuple[str, Path | None]:
    if value.startswith("#") or value.startswith("mailto:") or value.startswith("tel:"):
        return "skip", None
    if value.startswith("data:"):
        return "data", None
    if value.startswith("//"):
        return "external", None
    parsed = urlsplit(value)
    if parsed.scheme:
        return "external", None
    reference_path = unquote(parsed.path)
    if not reference_path:
        return "skip", None
    if reference_path.startswith(("/", "\\")):
        return "absolute", None
    return "local", (source_path.parent / reference_path).resolve()


def _validate_source_file(
    path: Path,
    root: Path,
    issues: list[Issue],
    artifact_dir: Path | None = None,
    artifact_type: str | None = None,
) -> set[Path]:
    location = _relative(root, path)
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        _add(issues, "error", "encoding", location, f"El archivo no es UTF-8: {error}.")
        return set()
    except OSError as error:
        _add(issues, "error", "source-read", location, str(error))
        return set()

    if "/BibliotecaWeb/" in source:
        _add(issues, "error", "repository-name-path", location, "No se debe codificar el nombre del repositorio en rutas públicas.")
    for pattern, code, message in (
        (r"\binnerHTML\b", "unsafe-inner-html", "No se permite innerHTML; usa APIs DOM seguras."),
        (r"\beval\s*\(", "unsafe-eval", "No se permite eval()."),
        (r"\bnew\s+Function\b", "unsafe-function", "No se permite new Function()."),
    ):
        if re.search(pattern, source):
            _add(issues, "error", code, location, message)
    if "-----BEGIN PRIVATE KEY-----" in source:
        _add(issues, "error", "secret-private-key", location, "El archivo contiene una clave privada.")
    data_uris = re.findall(r"data:[^\s\"')]+", source)
    if any(len(value) > WARNING_BASE64_CHARS for value in data_uris):
        _add(issues, "warning", "large-base64", location, "Contiene un recurso Base64 grande; usa un archivo optimizado.")

    references, parser = _extract_references(path, source)
    referenced_paths: set[Path] = set()
    if parser:
        duplicate_ids = sorted({element_id for element_id in parser.ids if parser.ids.count(element_id) > 1})
        for element_id in duplicate_ids:
            _add(issues, "error", "html-id-duplicate", location, f"El id HTML '{element_id}' está duplicado.")
        if path.name == "index.html":
            if parser.main_count != 1:
                _add(issues, "error", "html-main", location, f"Se esperaba un main y se encontraron {parser.main_count}.")
            if parser.h1_count != 1:
                _add(issues, "error", "html-h1", location, f"Se esperaba un h1 y se encontraron {parser.h1_count}.")
            if parser.html_lang != "es":
                _add(issues, "error", "html-lang", location, "El documento debe declarar lang=\"es\".")
            if parser.title_count != 1:
                _add(issues, "error", "html-title", location, f"Se esperaba un title y se encontraron {parser.title_count}.")
            if not parser.has_viewport:
                _add(issues, "error", "html-viewport", location, "El documento necesita meta viewport.")
            if parser.buttons_without_type:
                _add(issues, "error", "button-type", location, f"Hay {parser.buttons_without_type} botones sin atributo type.")
            for before, after in zip(parser.headings, parser.headings[1:]):
                if after > before + 1:
                    _add(issues, "error", "heading-order", location, f"La jerarquía salta de h{before} a h{after}.")
                    break
        known_ids = set(parser.ids)
        for attribute, target in parser.aria_references:
            if target not in known_ids:
                _add(issues, "error", "aria-reference", location, f"{attribute} apunta al id inexistente '{target}'.")
        for target in parser.label_targets:
            if target not in known_ids:
                _add(issues, "error", "label-reference", location, f"label apunta al id inexistente '{target}'.")
        for image in parser.images_without_alt:
            _add(issues, "error", "image-alt", location, f"La imagen '{image}' necesita atributo alt.")

    artifacts_root = root / "artefactos"
    for kind, value in references:
        ref_type, target = _resolve_reference(value, path)
        if ref_type == "absolute":
            _add(issues, "error", "absolute-public-path", location, f"La referencia '{value}' debe ser relativa.")
            continue
        if ref_type == "external":
            if kind == "resource":
                _add(issues, "warning", "external-resource", location, f"Recurso externo no vendorizado: '{value}'.")
            continue
        if ref_type in {"skip", "data"} or target is None:
            continue
        referenced_paths.add(target)
        if not _inside(target, root):
            _add(issues, "error", "reference-outside-project", location, f"La referencia '{value}' sale del proyecto.")
            continue
        if not target.exists():
            _add(issues, "error", "resource-missing", location, f"No existe el destino local '{value}'.")
            continue
        if artifact_dir:
            if _inside(target, artifacts_root) and not _inside(target, artifact_dir):
                _add(issues, "error", "cross-artifact-reference", location, f"No se puede importar otro artefacto: '{value}'.")
            if _inside(target, root / "app"):
                _add(issues, "error", "artifact-portal-dependency", location, f"Un artefacto no puede importar el portal: '{value}'.")
            if artifact_type in {"page", "mockup"} and any(
                _inside(target, root / folder) for folder in ("runtime", "brands", "vendor")
            ):
                _add(issues, "error", "artifact-type-dependency", location, f"El tipo '{artifact_type}' no puede cargar '{value}'.")
            if artifact_type == "presentation" and any(
                _inside(target, root / folder) for folder in ("brands", "vendor")
            ):
                _add(issues, "error", "presentation-internal-dependency", location, f"La presentación debe cargar el brand o motor mediante el runtime: '{value}'.")
    return referenced_paths


def _validate_artifacts(
    root: Path,
    catalog: dict[str, object] | None,
    issues: list[Issue],
) -> tuple[int, int]:
    if not catalog:
        return 0, 0
    artifacts = catalog.get("artifacts")
    if not isinstance(artifacts, list):
        return 0, 0
    artifact_count = 0
    presentation_count = 0
    for index, raw in enumerate(artifacts):
        if not isinstance(raw, dict):
            continue
        area_id = raw.get("areaId")
        collection_id = raw.get("collectionId")
        slug_value = raw.get("slug")
        artifact_type = raw.get("type")
        artifact_id = raw.get("id")
        if not all(isinstance(value, str) for value in (area_id, collection_id, slug_value, artifact_type, artifact_id)):
            continue
        artifact_dir = root / "artefactos" / area_id / collection_id / slug_value
        if not artifact_dir.is_dir():
            continue
        artifact_count += 1
        index_path = artifact_dir / "index.html"
        if artifact_type == "presentation":
            presentation_count += 1
            config_path = artifact_dir / "presentation.config.json"
            _validate_presentation_config(config_path, root, issues, expected_id=artifact_id)
            if not (artifact_dir / "presentation.css").is_file():
                _add(issues, "error", "presentation-css-missing", _relative(root, artifact_dir / "presentation.css"), "La presentación requiere presentation.css.")
            if index_path.is_file():
                _validate_presentation_markup(index_path, root, issues)

        referenced: set[Path] = set()
        for source_path in sorted(
            path for path in artifact_dir.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        ):
            referenced.update(
                _validate_source_file(
                    source_path,
                    root,
                    issues,
                    artifact_dir=artifact_dir,
                    artifact_type=artifact_type,
                )
            )
        if artifact_type == "mockup":
            source = "\n".join(
                path.read_text(encoding="utf-8")
                for path in artifact_dir.rglob("*.js")
                if path.is_file()
            )
            if "localStorage" in source and f"biblioteca:{artifact_id}:" not in source:
                _add(issues, "error", "mockup-storage-namespace", _relative(root, artifact_dir), f"Las claves localStorage deben comenzar con 'biblioteca:{artifact_id}:'.")
        assets_dir = artifact_dir / "assets"
        if assets_dir.is_dir():
            for asset in sorted(path for path in assets_dir.rglob("*") if path.is_file()):
                if asset.resolve() not in referenced:
                    _add(issues, "warning", "asset-unreferenced", _relative(root, asset), "El asset no aparece referenciado por el artefacto.")
        if any(
            placeholder in path.read_text(encoding="utf-8", errors="ignore")
            for path in artifact_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in {".html", ".json"}
            for placeholder in ("Nombre del estudiante", "Título de la presentación", "Título académico")
        ):
            _add(issues, "warning", "artifact-placeholder", _relative(root, artifact_dir), "El artefacto conserva texto de template por reemplazar.")
    return artifact_count, presentation_count


def _validate_brands(root: Path, issues: list[Issue]) -> int:
    brands_root = root / "brands"
    if not brands_root.is_dir():
        return 0
    count = 0
    for brand_dir in sorted(path for path in brands_root.iterdir() if path.is_dir()):
        count += 1
        location = _relative(root, brand_dir)
        if not SLUG_PATTERN.fullmatch(brand_dir.name):
            _add(issues, "error", "brand-slug", location, "La carpeta del brand debe usar un slug válido.")
        for filename in ("brand.css", "brand.js", "VERSION"):
            if not (brand_dir / filename).is_file():
                _add(issues, "error", "brand-file-missing", f"{location}/{filename}", "El archivo del brand es obligatorio.")
        js_path = brand_dir / "brand.js"
        if js_path.is_file():
            source = js_path.read_text(encoding="utf-8", errors="replace")
            for token in ("mountBrand", "update", "destroy"):
                if token not in source:
                    _add(issues, "error", "brand-contract", _relative(root, js_path), f"El módulo no contiene '{token}'.")
            if "Reveal" in source or "runtime/presentation" in source:
                _add(issues, "error", "brand-engine-dependency", _relative(root, js_path), "El brand no debe acceder al motor o runtime.")
        for source_path in sorted(
            path for path in brand_dir.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        ):
            _validate_source_file(source_path, root, issues)
    return count


def _validate_templates(root: Path, issues: list[Issue]) -> int:
    templates_root = root / "templates" / "presentation" / "v1"
    if not templates_root.is_dir():
        return 0
    count = 0
    for template_dir in sorted(path for path in templates_root.iterdir() if path.is_dir()):
        count += 1
        location = _relative(root, template_dir)
        if not SLUG_PATTERN.fullmatch(template_dir.name):
            _add(issues, "error", "template-slug", location, "La carpeta del template debe usar un slug válido.")
        for filename in ("index.html", "presentation.css", "presentation.config.json", "TEMPLATE.md"):
            if not (template_dir / filename).is_file():
                _add(issues, "error", "template-file-missing", f"{location}/{filename}", "El archivo del template es obligatorio.")
        config = _validate_presentation_config(template_dir / "presentation.config.json", root, issues)
        if config and not str(config.get("presentationId", "")).startswith("template-"):
            _add(issues, "error", "template-id", f"{location}/presentation.config.json.presentationId", "El ID de ejemplo debe comenzar con 'template-'.")
        html_path = template_dir / "index.html"
        if html_path.is_file():
            _validate_presentation_markup(html_path, root, issues)
        for source_path in sorted(
            path for path in template_dir.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        ):
            referenced = _validate_source_file(source_path, root, issues)
            if any(_inside(target, templates_root) and not _inside(target, template_dir) for target in referenced):
                _add(issues, "error", "cross-template-reference", _relative(root, source_path), "Un template no puede importar otro template.")
    return count


def _validate_shared_sources(root: Path, issues: list[Issue]) -> None:
    root_index = root / "index.html"
    if root_index.is_file():
        _validate_source_file(root_index, root, issues)
    for folder in ("app", "estado", "runtime", "shared"):
        base = root / folder
        if not base.is_dir():
            continue
        for source_path in sorted(
            path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        ):
            _validate_source_file(source_path, root, issues)


def _validate_stats(root: Path, issues: list[Issue]) -> None:
    stats_path = root / "data" / "stats.json"
    policy_path = root / "data" / "storage-policy.json"
    try:
        from project_stats import StatsError, calculate_stats, load_policy
    except ImportError as error:
        _add(issues, "error", "stats-tool-import", "tools/project_stats.py", str(error))
        return

    try:
        load_policy(root)
    except StatsError as error:
        _add(issues, "error", "policy-invalid", _relative(root, policy_path), str(error))
        return

    if not stats_path.is_file():
        _add(issues, "error", "stats-file-missing", _relative(root, stats_path), "Ejecuta tools/build_stats.py.")
        return
    try:
        stored = json.loads(stats_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _add(issues, "error", "stats-json", _relative(root, stats_path), str(error))
        return
    if not isinstance(stored, dict):
        _add(issues, "error", "stats-schema", _relative(root, stats_path), "Debe contener un objeto JSON.")
        return
    if stored.get("schemaVersion") != 1 or stored.get("scope") != "public-static-files":
        _add(issues, "error", "stats-version", _relative(root, stats_path), "La versión o alcance no es compatible.")
        return
    generated_at = stored.get("generatedAt")
    if not isinstance(generated_at, str):
        _add(issues, "error", "stats-date", f"{_relative(root, stats_path)}.generatedAt", "Debe ser una fecha ISO con zona horaria.")
        return
    try:
        parsed_date = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if parsed_date.tzinfo is None:
            raise ValueError("sin zona horaria")
    except ValueError:
        _add(issues, "error", "stats-date", f"{_relative(root, stats_path)}.generatedAt", "Debe ser una fecha ISO válida con zona horaria.")
        return
    try:
        current = calculate_stats(root, generated_at=generated_at)
    except StatsError as error:
        _add(issues, "error", "stats-calculation", _relative(root, stats_path), str(error))
        return
    if stored != current:
        _add(
            issues,
            "error",
            "stats-stale",
            _relative(root, stats_path),
            "No corresponde a los archivos o la política actuales; ejecuta tools/build_stats.py.",
        )


def _validate_files(root: Path, issues: list[Issue]) -> int:
    checked = 0
    ignored_parts = {".git", "__pycache__"}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if any(part in ignored_parts for part in path.parts):
            continue
        checked += 1
        location = _relative(root, path)
        if path.is_symlink():
            _add(issues, "warning", "symlink", location, "Los symlinks pueden no publicarse como se espera.")
        size = path.stat().st_size
        if size > ERROR_FILE_BYTES:
            _add(issues, "error", "file-too-large", location, f"Pesa {size} bytes y supera 50 MiB.")
        elif size > WARNING_FILE_BYTES:
            _add(issues, "warning", "file-large", location, f"Pesa {size} bytes y supera 5 MiB.")
        lowered = path.name.lower()
        if lowered in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES:
            _add(issues, "error", "sensitive-file", location, "El nombre indica un posible secreto o dato privado.")
    return checked


def validate_project(root: Path | str | None = None) -> ValidationResult:
    selected_root = Path(root).resolve() if root else project_root_from_tools()
    issues: list[Issue] = []
    if not selected_root.is_dir():
        _add(issues, "error", "root-missing", str(selected_root), "La raíz del proyecto no existe.")
        return ValidationResult(selected_root, issues)

    for required in (
        "index.html",
        "AGENTS.md",
        "data/catalog.json",
        "data/stats.json",
        "data/storage-policy.json",
        "schemas/catalog.schema.json",
        "schemas/presentation-config.schema.json",
        "schemas/stats.schema.json",
        "schemas/storage-policy.schema.json",
    ):
        if not (selected_root / required).is_file():
            _add(issues, "error", "project-file-missing", required, "El archivo base es obligatorio.")

    catalog, _ = _validate_catalog(selected_root, issues)
    artifact_count, presentation_count = _validate_artifacts(selected_root, catalog, issues)
    brand_count = _validate_brands(selected_root, issues)
    template_count = _validate_templates(selected_root, issues)
    _validate_shared_sources(selected_root, issues)
    _validate_stats(selected_root, issues)
    checked_files = _validate_files(selected_root, issues)

    issues.sort(key=lambda issue: (0 if issue.severity == "error" else 1, issue.location, issue.code))
    return ValidationResult(
        root=selected_root,
        issues=issues,
        artifact_count=artifact_count,
        presentation_count=presentation_count,
        template_count=template_count,
        brand_count=brand_count,
        checked_files=checked_files,
    )
