const root = document.querySelector("[data-presentation-root]");
const scene = root?.querySelector("[data-evidence-scene]");
const caption = root?.querySelector("[data-evidence-caption]");

const captions = {
  none: "Avanza para construir una evidencia defendible.",
  contextual: "Primero: ubicar el hecho dentro de su contexto.",
  corroborada: "Después: contrastarlo con una fuente independiente.",
  trazable: "Finalmente: conservar una ruta que permita verificarlo.",
};

function renderEvidenceScene() {
  if (!scene || !caption) return;

  const visibleLevels = Array.from(
    scene.querySelectorAll("[data-evidence-level].visible"),
  );
  const activeLevel = visibleLevels.at(-1)?.dataset.evidenceLevel || "none";

  scene.dataset.activeLevel = activeLevel;
  caption.textContent = captions[activeLevel];
}

root?.addEventListener("pc:ready", renderEvidenceScene);
root?.addEventListener("pc:stepchange", (event) => {
  if (event.detail.current.slideId === "evidencia") {
    renderEvidenceScene();
  }
});
root?.addEventListener("pc:slideenter", (event) => {
  if (event.detail.current.slideId === "evidencia") {
    renderEvidenceScene();
  }
});
