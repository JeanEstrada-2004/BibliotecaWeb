const layers = {
  portal: {
    label: "Capa de descubrimiento",
    title: "Portal",
    description: "Organiza áreas, colecciones y resultados para ayudar a encontrar cada pieza.",
    knows: "El catálogo público",
    ignores: "La implementación interna de cada artefacto",
  },
  catalogo: {
    label: "Capa de clasificación",
    title: "Catálogo",
    description: "Describe qué existe y dónde vive mediante datos pequeños, legibles y validables.",
    knows: "IDs, tipos, áreas, colecciones y slugs",
    ignores: "Diseño, animaciones y lógica interna",
  },
  artefacto: {
    label: "Unidad de contenido",
    title: "Artefacto",
    description: "Conserva su propia experiencia visual y funciona como una página estática independiente.",
    knows: "Sus archivos, recursos y comportamiento",
    ignores: "El código del portal y otros artefactos",
  },
};

const tabs = [...document.querySelectorAll("[role='tab'][data-layer]")];
const panel = document.querySelector("#layer-detail");
const label = document.querySelector("#layer-label");
const title = document.querySelector("#layer-title");
const description = document.querySelector("#layer-description");
const knows = document.querySelector("#layer-knows");
const ignores = document.querySelector("#layer-ignores");

function selectLayer(layerId, { moveFocus = false } = {}) {
  const layer = layers[layerId];
  const activeTab = tabs.find((tab) => tab.dataset.layer === layerId);

  if (!layer || !activeTab) {
    return;
  }

  for (const tab of tabs) {
    const selected = tab === activeTab;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }

  panel.setAttribute("aria-labelledby", activeTab.id);
  panel.dataset.layer = layerId;
  label.textContent = layer.label;
  title.textContent = layer.title;
  description.textContent = layer.description;
  knows.textContent = layer.knows;
  ignores.textContent = layer.ignores;

  if (moveFocus) {
    activeTab.focus();
  }
}

function moveSelection(currentIndex, direction) {
  const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
  selectLayer(tabs[nextIndex].dataset.layer, { moveFocus: true });
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => {
    selectLayer(tab.dataset.layer);
  });

  tab.addEventListener("keydown", (event) => {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      moveSelection(index, 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      moveSelection(index, -1);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectLayer(tabs[0].dataset.layer, { moveFocus: true });
    } else if (event.key === "End") {
      event.preventDefault();
      selectLayer(tabs.at(-1).dataset.layer, { moveFocus: true });
    }
  });
});
