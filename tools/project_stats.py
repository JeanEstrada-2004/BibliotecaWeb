from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path


PUBLIC_DIRECTORIES = {
    "app",
    "artefactos",
    "brands",
    "data",
    "estado",
    "runtime",
    "shared",
    "vendor",
}
EXCLUDED_ROOT_FILES = {".gitignore", "AGENTS.md", "README.md"}
GENERATED_STATS_PATH = "data/stats.json"


class StatsError(RuntimeError):
    """Error legible producido al calcular la huella de BibliotecaWeb."""


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StatsError(f"No se pudo leer {label}: {error}") from error
    if not isinstance(value, dict):
        raise StatsError(f"{label} debe contener un objeto JSON.")
    return value


def load_catalog(root: Path) -> dict[str, object]:
    catalog = _read_json(root / "data" / "catalog.json", "data/catalog.json")
    for key in ("areas", "collections", "types", "artifacts"):
        if not isinstance(catalog.get(key), list):
            raise StatsError(f"data/catalog.json.{key} debe ser un arreglo.")
    return catalog


def load_policy(root: Path) -> dict[str, object]:
    policy = _read_json(root / "data" / "storage-policy.json", "data/storage-policy.json")
    if policy.get("schemaVersion") != 1:
        raise StatsError("data/storage-policy.json.schemaVersion debe ser 1.")
    if policy.get("kind") != "internal-maintenance":
        raise StatsError("data/storage-policy.json.kind debe ser internal-maintenance.")

    for key in (
        "budgetBytes",
        "fileWarningBytes",
        "artifactWarningBytes",
        "duplicateMinimumBytes",
        "concentrationPercentage",
        "minimumArtifactsForConcentration",
        "topItemsLimit",
    ):
        value = policy.get(key)
        if type(value) is not int or value < 0:
            raise StatsError(f"data/storage-policy.json.{key} debe ser un entero no negativo.")
    if policy["budgetBytes"] < 1:
        raise StatsError("data/storage-policy.json.budgetBytes debe ser mayor que cero.")
    if not 1 <= policy["concentrationPercentage"] <= 100:
        raise StatsError("concentrationPercentage debe estar entre 1 y 100.")
    if policy["topItemsLimit"] < 1:
        raise StatsError("topItemsLimit debe ser mayor que cero.")

    levels = policy.get("levels")
    if not isinstance(levels, list) or not levels:
        raise StatsError("data/storage-policy.json.levels debe ser un arreglo no vacío.")
    seen_ids: set[str] = set()
    previous_minimum = -1
    for index, level in enumerate(levels):
        location = f"data/storage-policy.json.levels[{index}]"
        if not isinstance(level, dict):
            raise StatsError(f"{location} debe ser un objeto.")
        level_id = level.get("id")
        minimum = level.get("minPercentage")
        if not isinstance(level_id, str) or not level_id:
            raise StatsError(f"{location}.id debe contener texto.")
        if level_id in seen_ids:
            raise StatsError(f"{location}.id está duplicado.")
        if type(minimum) is not int or minimum < 0 or minimum <= previous_minimum:
            raise StatsError(f"{location}.minPercentage debe crecer de forma estricta.")
        for key in ("label", "tone", "message"):
            if not isinstance(level.get(key), str) or not str(level[key]).strip():
                raise StatsError(f"{location}.{key} debe contener texto.")
        seen_ids.add(level_id)
        previous_minimum = minimum
    if levels[0].get("minPercentage") != 0:
        raise StatsError("El primer nivel de la política debe comenzar en 0%.")
    return policy


def iter_public_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for item in root.iterdir():
        if item.is_file() and item.name not in EXCLUDED_ROOT_FILES and item.suffix.lower() != ".md":
            files.append(item)
    for directory_name in sorted(PUBLIC_DIRECTORIES):
        directory = root / directory_name
        if not directory.is_dir():
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(
        {
            path.resolve()
            for path in files
            if path.relative_to(root).as_posix() != GENERATED_STATS_PATH
            and ".git" not in path.parts
            and "__pycache__" not in path.parts
        },
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _file_records(root: Path) -> tuple[list[dict[str, object]], str]:
    records: list[dict[str, object]] = []
    fingerprint = hashlib.sha256()
    for path in iter_public_files(root):
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        size = len(content)
        fingerprint.update(relative.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(digest.encode("ascii"))
        fingerprint.update(b"\n")
        records.append({"path": relative, "bytes": size, "sha256": digest})
    return records, fingerprint.hexdigest()


def _percentage(value: int, total: int) -> float:
    return round((value / total) * 100, 2) if total else 0.0


def _status_for(percentage: float, policy: dict[str, object]) -> dict[str, object]:
    levels = policy["levels"]
    selected = levels[0]
    for level in levels:
        if percentage >= level["minPercentage"]:
            selected = level
        else:
            break
    return {
        "id": selected["id"],
        "label": selected["label"],
        "tone": selected["tone"],
        "message": selected["message"],
    }


def _component_for(path: str) -> str:
    first = path.split("/", 1)[0]
    if first == "artefactos":
        return "artifacts"
    if first == "app" or "/" not in path:
        return "portal"
    return {
        "brands": "brands",
        "data": "data",
        "estado": "status-page",
        "runtime": "runtime",
        "shared": "shared",
        "vendor": "vendor",
    }.get(first, "other")


def _sorted_breakdown(
    items: list[dict[str, object]],
    byte_map: dict[str, int],
    total: int,
) -> list[dict[str, object]]:
    result = [
        {
            "id": str(item["id"]),
            "label": str(item.get("label") or item["id"]),
            "bytes": byte_map.get(str(item["id"]), 0),
            "percentage": _percentage(byte_map.get(str(item["id"]), 0), total),
        }
        for item in items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    return sorted(result, key=lambda item: (-int(item["bytes"]), str(item["label"])))


def _artifact_records(
    catalog: dict[str, object],
    files: list[dict[str, object]],
) -> list[dict[str, object]]:
    areas = {
        item["id"]: item.get("label", item["id"])
        for item in catalog["areas"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    types = {
        item["id"]: item.get("label", item["id"])
        for item in catalog["types"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    records: list[dict[str, object]] = []
    for artifact in catalog["artifacts"]:
        if not isinstance(artifact, dict):
            continue
        area_id = artifact.get("areaId")
        collection_id = artifact.get("collectionId")
        slug = artifact.get("slug")
        if not all(isinstance(value, str) for value in (area_id, collection_id, slug)):
            continue
        directory = f"artefactos/{area_id}/{collection_id}/{slug}"
        prefix = f"{directory}/"
        artifact_files = [file for file in files if str(file["path"]).startswith(prefix)]
        size = sum(int(file["bytes"]) for file in artifact_files)
        records.append(
            {
                "id": str(artifact.get("id") or slug),
                "title": str(artifact.get("title") or slug),
                "areaId": area_id,
                "areaLabel": str(areas.get(area_id, area_id)),
                "type": str(artifact.get("type") or "unknown"),
                "typeLabel": str(types.get(str(artifact.get("type")), artifact.get("type") or "Otro")),
                "status": str(artifact.get("status") or "draft"),
                "path": directory,
                "bytes": size,
                "fileCount": len(artifact_files),
            }
        )
    total = sum(int(record["bytes"]) for record in records)
    for record in records:
        record["percentageOfArtifacts"] = _percentage(int(record["bytes"]), total)
    return sorted(records, key=lambda item: (-int(item["bytes"]), str(item["title"])))


def _duplicates(files: list[dict[str, object]], minimum_bytes: int) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for record in files:
        if int(record["bytes"]) >= minimum_bytes:
            groups[str(record["sha256"])].append(record)
    duplicates = [
        {
            "sha256": digest,
            "bytesEach": int(group[0]["bytes"]),
            "copies": len(group),
            "repeatedBytes": int(group[0]["bytes"]) * (len(group) - 1),
            "paths": sorted(str(record["path"]) for record in group),
        }
        for digest, group in groups.items()
        if len(group) > 1
    ]
    return sorted(duplicates, key=lambda item: (-int(item["repeatedBytes"]), str(item["sha256"])))


def _warnings(
    policy: dict[str, object],
    files: list[dict[str, object]],
    artifacts: list[dict[str, object]],
    areas: list[dict[str, object]],
    types: list[dict[str, object]],
    duplicates: list[dict[str, object]],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    for record in files:
        if int(record["bytes"]) > int(policy["fileWarningBytes"]):
            warnings.append(
                {
                    "code": "large-file",
                    "severity": "warning",
                    "location": str(record["path"]),
                    "message": f"El archivo pesa {record['bytes']} bytes y supera la política interna por archivo.",
                }
            )
    for artifact in artifacts:
        if int(artifact["bytes"]) > int(policy["artifactWarningBytes"]):
            warnings.append(
                {
                    "code": "large-artifact",
                    "severity": "warning",
                    "location": str(artifact["path"]),
                    "message": f"El artefacto pesa {artifact['bytes']} bytes y supera la política interna por artefacto.",
                }
            )
    if len(artifacts) >= int(policy["minimumArtifactsForConcentration"]):
        threshold = float(policy["concentrationPercentage"])
        for kind, records in (("area", areas), ("type", types)):
            if records and float(records[0]["percentage"]) >= threshold:
                warnings.append(
                    {
                        "code": f"{kind}-concentration",
                        "severity": "warning",
                        "location": str(records[0]["id"]),
                        "message": f"{records[0]['label']} concentra {records[0]['percentage']}% del peso de artefactos.",
                    }
                )
    for duplicate in duplicates:
        warnings.append(
            {
                "code": "duplicate-files",
                "severity": "warning",
                "location": str(duplicate["paths"][0]),
                "message": f"Hay {duplicate['copies']} copias exactas de un archivo de {duplicate['bytesEach']} bytes.",
            }
        )
    return sorted(warnings, key=lambda item: (item["code"], item["location"]))


def calculate_stats(
    root: Path | str,
    generated_at: str | None = None,
) -> dict[str, object]:
    selected_root = Path(root).resolve()
    catalog = load_catalog(selected_root)
    policy = load_policy(selected_root)
    files, source_fingerprint = _file_records(selected_root)
    artifacts = _artifact_records(catalog, files)
    artifact_bytes = sum(int(record["bytes"]) for record in artifacts)
    total_bytes = sum(int(record["bytes"]) for record in files)

    area_bytes: dict[str, int] = defaultdict(int)
    type_bytes: dict[str, int] = defaultdict(int)
    for record in artifacts:
        area_bytes[str(record["areaId"])] += int(record["bytes"])
        type_bytes[str(record["type"])] += int(record["bytes"])
    areas = _sorted_breakdown(catalog["areas"], area_bytes, artifact_bytes)
    types = _sorted_breakdown(catalog["types"], type_bytes, artifact_bytes)

    component_bytes: dict[str, int] = defaultdict(int)
    for record in files:
        component_bytes[_component_for(str(record["path"]))] += int(record["bytes"])
    component_labels = {
        "artifacts": "Artefactos",
        "portal": "Portal",
        "status-page": "Página de estado",
        "runtime": "Presentation Runtime",
        "brands": "Brands",
        "vendor": "Dependencias versionadas",
        "data": "Datos",
        "shared": "Recursos compartidos",
        "other": "Otros",
    }
    components = sorted(
        (
            {
                "id": component,
                "label": component_labels[component],
                "bytes": size,
                "percentage": _percentage(size, total_bytes),
            }
            for component, size in component_bytes.items()
        ),
        key=lambda item: (-int(item["bytes"]), str(item["label"])),
    )

    duplicate_groups = _duplicates(files, int(policy["duplicateMinimumBytes"]))
    warnings = _warnings(policy, files, artifacts, areas, types, duplicate_groups)
    budget_bytes = int(policy["budgetBytes"])
    budget_percentage = round((total_bytes / budget_bytes) * 100, 2)
    status = _status_for(budget_percentage, policy)
    limit = int(policy["topItemsLimit"])
    timestamp = generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "schemaVersion": 1,
        "scope": "public-static-files",
        "generatedAt": timestamp,
        "sourceFingerprint": source_fingerprint,
        "policy": {
            "kind": policy["kind"],
            "label": policy["label"],
            "budgetBytes": budget_bytes,
            "budgetPercentage": budget_percentage,
            "status": status,
        },
        "summary": {
            "totalBytes": total_bytes,
            "artifactBytes": artifact_bytes,
            "sharedBytes": total_bytes - artifact_bytes,
            "artifactCount": len(artifacts),
            "publishedArtifactCount": sum(1 for item in artifacts if item["status"] == "published"),
            "fileCount": len(files),
            "warningCount": len(warnings),
        },
        "breakdown": {
            "areas": areas,
            "types": types,
            "components": components,
        },
        "artifacts": artifacts,
        "largestFiles": sorted(files, key=lambda item: (-int(item["bytes"]), str(item["path"])))[:limit],
        "duplicates": duplicate_groups[:limit],
        "warnings": warnings,
        "measurement": {
            "includedDirectories": sorted(PUBLIC_DIRECTORIES),
            "excludedGeneratedFiles": [GENERATED_STATS_PATH],
            "note": "Mide la huella web publicable; excluye documentación, schemas, templates y herramientas.",
        },
    }


def write_stats(root: Path | str, generated_at: str | None = None) -> dict[str, object]:
    selected_root = Path(root).resolve()
    stats = calculate_stats(selected_root, generated_at=generated_at)
    destination = selected_root / GENERATED_STATS_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / ".stats-writing.tmp"
    temporary.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return stats
