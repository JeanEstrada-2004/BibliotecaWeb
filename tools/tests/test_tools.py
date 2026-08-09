from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROOT = PROJECT_ROOT / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import create_artifact as creator
from project_stats import calculate_stats, write_stats
from project_validation import Issue, ValidationResult, validate_project


def copy_project(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", "__pycache__"}}

    shutil.copytree(source, destination, ignore=ignore)


class ProjectValidationTests(unittest.TestCase):
    def test_current_project_has_no_errors(self) -> None:
        result = validate_project(PROJECT_ROOT)
        self.assertEqual([], result.errors)

    def test_invalid_date_reports_exact_catalog_field(self) -> None:
        with tempfile.TemporaryDirectory(prefix="biblioteca-validator-test-") as temporary:
            root = Path(temporary) / "BibliotecaWeb"
            copy_project(PROJECT_ROOT, root)
            catalog_path = root / "data" / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["artifacts"][0]["publishedAt"] = "2026-99-99"
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

            result = validate_project(root)

            issue = next(item for item in result.errors if item.code == "date")
            self.assertEqual("data/catalog.json.artifacts[0].publishedAt", issue.location)

    def test_missing_aria_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="biblioteca-aria-test-") as temporary:
            root = Path(temporary) / "BibliotecaWeb"
            copy_project(PROJECT_ROOT, root)
            index_path = root / "index.html"
            source = index_path.read_text(encoding="utf-8")
            source = source.replace('aria-labelledby="hero-title"', 'aria-labelledby="titulo-inexistente"', 1)
            index_path.write_text(source, encoding="utf-8")

            result = validate_project(root)

            issue = next(item for item in result.errors if item.code == "aria-reference")
            self.assertEqual("index.html", issue.location)
            self.assertIn("titulo-inexistente", issue.message)

    def test_presentation_rejects_external_home_href(self) -> None:
        with tempfile.TemporaryDirectory(prefix="biblioteca-home-test-") as temporary:
            root = Path(temporary) / "BibliotecaWeb"
            copy_project(PROJECT_ROOT, root)
            config_path = (
                root
                / "artefactos"
                / "ciclo-09"
                / "seguridad-auditoria"
                / "introduccion-auditoria-sistemas"
                / "presentation.config.json"
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["homeHref"] = "https://example.com/"
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            result = validate_project(root)

            issue = next(item for item in result.errors if item.code == "presentation-home-href")
            self.assertTrue(issue.location.endswith("presentation.config.json.homeHref"))

    def test_runtime_disables_overview_and_creates_home_control(self) -> None:
        source = (PROJECT_ROOT / "runtime" / "presentation" / "v1" / "runtime.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("overview: false", source)
        self.assertIn('link.className = "pc-home-control"', source)


class ProjectStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="biblioteca-stats-test-")
        self.root = Path(self.temporary.name) / "BibliotecaWeb"
        copy_project(PROJECT_ROOT, self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_stored_stats_match_public_files_and_catalog(self) -> None:
        stored = json.loads((self.root / "data" / "stats.json").read_text(encoding="utf-8"))
        current = calculate_stats(self.root, generated_at=stored["generatedAt"])

        self.assertEqual(stored, current)
        self.assertEqual(2, current["summary"]["artifactCount"])
        self.assertEqual("excellent", current["policy"]["status"]["id"])
        self.assertEqual(
            {"ciclo-09", "ciclo-10", "trabajo", "personal"},
            {item["id"] for item in current["breakdown"]["areas"]},
        )

    def test_public_change_is_stale_until_stats_are_rebuilt(self) -> None:
        portal_css = self.root / "app" / "portal.css"
        portal_css.write_text(portal_css.read_text(encoding="utf-8") + "\n", encoding="utf-8")

        stale = validate_project(self.root)
        self.assertTrue(any(issue.code == "stats-stale" for issue in stale.errors))

        write_stats(self.root, generated_at="2026-08-09T00:00:00Z")
        self.assertEqual([], validate_project(self.root).errors)


class ArtifactCreationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="biblioteca-creator-test-")
        self.root = Path(self.temporary.name) / "BibliotecaWeb"
        copy_project(PROJECT_ROOT, self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def page_spec(self, slug: str = "pagina-de-prueba") -> creator.ArtifactSpec:
        return creator.ArtifactSpec(
            artifact_type="page",
            area_id="personal",
            collection_id="general",
            slug=slug,
            title="Página de prueba",
            summary="Artefacto temporal para comprobar la herramienta.",
            tags=("prueba", "herramientas"),
        )

    def test_dry_run_does_not_modify_project(self) -> None:
        catalog_path = self.root / "data" / "catalog.json"
        before = catalog_path.read_bytes()

        result = creator.create_artifact(self.root, self.page_spec(), dry_run=True)

        self.assertTrue(result.dry_run)
        self.assertFalse(result.target.exists())
        self.assertEqual(before, catalog_path.read_bytes())

    def test_page_creation_writes_files_and_catalog(self) -> None:
        result = creator.create_artifact(self.root, self.page_spec())

        self.assertFalse(result.dry_run)
        self.assertTrue((result.target / "index.html").is_file())
        self.assertTrue((result.target / "styles.css").is_file())
        self.assertTrue((result.target / "script.js").is_file())
        catalog = json.loads((self.root / "data" / "catalog.json").read_text(encoding="utf-8"))
        self.assertTrue(any(item["id"] == result.artifact_id for item in catalog["artifacts"]))
        stats = json.loads((self.root / "data" / "stats.json").read_text(encoding="utf-8"))
        self.assertEqual(3, stats["summary"]["artifactCount"])
        self.assertEqual([], validate_project(self.root).errors)

        with self.assertRaisesRegex(creator.CreationError, "ya está registrado"):
            creator.create_artifact(self.root, self.page_spec())

    def test_academic_presentation_is_detached_from_template(self) -> None:
        spec = creator.ArtifactSpec(
            artifact_type="presentation",
            area_id="ciclo-09",
            collection_id="seguridad-auditoria",
            slug="presentacion-de-prueba",
            title="Presentación de prueba",
            summary="Presentación temporal para comprobar el copiado del template.",
            template="academic",
            brand_data={"author": "Autor de prueba"},
        )

        result = creator.create_artifact(self.root, spec)

        config = json.loads((result.target / "presentation.config.json").read_text(encoding="utf-8"))
        source = (result.target / "index.html").read_text(encoding="utf-8")
        self.assertEqual(result.artifact_id, config["presentationId"])
        self.assertEqual("Autor de prueba", config["brandData"]["author"])
        self.assertIn("<title>Presentación de prueba</title>", source)
        self.assertFalse((result.target / "TEMPLATE.md").exists())
        self.assertEqual([], validate_project(self.root).errors)

    def test_failed_final_validation_rolls_back_catalog_and_folder(self) -> None:
        catalog_path = self.root / "data" / "catalog.json"
        stats_path = self.root / "data" / "stats.json"
        before = catalog_path.read_bytes()
        stats_before = stats_path.read_bytes()
        good = validate_project(self.root)
        failed = ValidationResult(
            root=self.root,
            issues=[Issue("error", "forced-test", "artefactos/test", "Fallo final simulado.")],
        )

        with mock.patch.object(creator, "validate_project", side_effect=[good, failed]):
            with self.assertRaisesRegex(creator.CreationError, "forced-test"):
                creator.create_artifact(self.root, self.page_spec("rollback-de-prueba"))

        target = self.root / "artefactos" / "personal" / "general" / "rollback-de-prueba"
        self.assertFalse(target.exists())
        self.assertEqual(before, catalog_path.read_bytes())
        self.assertEqual(stats_before, stats_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
