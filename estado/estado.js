const refs = {
  hero: document.querySelector("[data-status-hero]"),
  statusMessage: document.querySelector("[data-status-message]"),
  statusChip: document.querySelector("[data-status-chip]"),
  totalSize: document.querySelector("[data-total-size]"),
  budgetLabel: document.querySelector("[data-budget-label]"),
  budgetProgress: document.querySelector("[data-budget-progress]"),
  budgetPercentage: document.querySelector("[data-budget-percentage]"),
  artifactCount: document.querySelector("[data-artifact-count]"),
  publishedCount: document.querySelector("[data-published-count]"),
  artifactSize: document.querySelector("[data-artifact-size]"),
  sharedSize: document.querySelector("[data-shared-size]"),
  generatedAt: document.querySelector("[data-generated-at]"),
  fileCount: document.querySelector("[data-file-count]"),
  areaBreakdown: document.querySelector("[data-area-breakdown]"),
  typeBreakdown: document.querySelector("[data-type-breakdown]"),
  componentBreakdown: document.querySelector("[data-component-breakdown]"),
  artifactTable: document.querySelector("[data-artifact-table]"),
  largestFiles: document.querySelector("[data-largest-files]"),
  warningCount: document.querySelector("[data-warning-count]"),
  warningList: document.querySelector("[data-warning-list]"),
  loadError: document.querySelector("[data-load-error]"),
  loadErrorMessage: document.querySelector("[data-load-error-message]"),
};

const byteFormatter = new Intl.NumberFormat("es-PE", {
  maximumFractionDigits: 1,
});

const dateFormatter = new Intl.DateTimeFormat("es-PE", {
  dateStyle: "medium",
  timeStyle: "short",
});

function createElement(tagName, options = {}, children = []) {
  const element = document.createElement(tagName);
  if (options.className) {
    element.className = options.className;
  }
  if (options.text !== undefined) {
    element.textContent = options.text;
  }
  for (const [name, value] of Object.entries(options.attributes ?? {})) {
    element.setAttribute(name, String(value));
  }
  for (const child of children) {
    if (child) {
      element.append(child);
    }
  }
  return element;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "—";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${byteFormatter.format(value)} ${unit}`;
}

function formatPercentage(value) {
  if (value > 0 && value < 0.01) {
    return "<0,01%";
  }
  return `${byteFormatter.format(value)}%`;
}

function validateStats(stats) {
  if (!stats || stats.schemaVersion !== 1 || stats.scope !== "public-static-files") {
    throw new Error("La versión de las estadísticas no es compatible.");
  }
  if (!stats.summary || !stats.policy?.status || !stats.breakdown) {
    throw new Error("El resumen de estadísticas está incompleto.");
  }
  for (const key of ["areas", "types", "components"]) {
    if (!Array.isArray(stats.breakdown[key])) {
      throw new Error(`No existe el desglose de ${key}.`);
    }
  }
  if (!Array.isArray(stats.artifacts) || !Array.isArray(stats.largestFiles)) {
    throw new Error("Las listas de detalle no son válidas.");
  }
}

function createBarRow(item) {
  const percentage = Math.min(Math.max(Number(item.percentage) || 0, 0), 100);
  const bar = createElement("span", {
    className: "bar-row__fill",
    attributes: { style: `--bar-value: ${percentage}%` },
  });
  return createElement("div", { className: "bar-row" }, [
    createElement("div", { className: "bar-row__labels" }, [
      createElement("strong", { text: item.label }),
      createElement("span", { text: formatBytes(item.bytes) }),
    ]),
    createElement("span", { className: "bar-row__track" }, [bar]),
    createElement("small", { text: formatPercentage(item.percentage) }),
  ]);
}

function renderBreakdown(container, items) {
  container.replaceChildren(...items.map(createBarRow));
}

function renderArtifacts(artifacts) {
  const rows = artifacts.map((artifact) =>
    createElement("tr", {}, [
      createElement("th", { text: artifact.title, attributes: { scope: "row" } }),
      createElement("td", { text: artifact.areaLabel }),
      createElement("td", { text: artifact.typeLabel }),
      createElement("td", { text: String(artifact.fileCount) }),
      createElement("td", { text: formatBytes(artifact.bytes) }),
    ]),
  );
  refs.artifactTable.replaceChildren(...rows);
}

function renderLargestFiles(files) {
  const items = files.map((file) =>
    createElement("li", {}, [
      createElement("code", { text: file.path }),
      createElement("strong", { text: formatBytes(file.bytes) }),
    ]),
  );
  refs.largestFiles.replaceChildren(...items);
}

function renderWarnings(warnings) {
  refs.warningCount.textContent = `${warnings.length} ${warnings.length === 1 ? "alerta" : "alertas"}`;
  if (warnings.length === 0) {
    refs.warningList.replaceChildren(
      createElement("div", { className: "alert alert--clear" }, [
        createElement("strong", { text: "Sin alertas activas" }),
        createElement("p", { text: "Ningún archivo o artefacto supera la política interna actual." }),
      ]),
    );
    return;
  }
  refs.warningList.replaceChildren(
    ...warnings.map((warning) =>
      createElement("div", { className: "alert" }, [
        createElement("strong", { text: warning.code }),
        createElement("code", { text: warning.location }),
        createElement("p", { text: warning.message }),
      ]),
    ),
  );
}

function renderStats(stats) {
  const { summary, policy, breakdown } = stats;
  const status = policy.status;
  const progressValue = Math.min(Math.max(policy.budgetPercentage, 0), 100);
  refs.hero.dataset.status = status.tone;
  refs.statusMessage.textContent = status.message;
  refs.statusChip.textContent = status.label;
  refs.totalSize.textContent = formatBytes(summary.totalBytes);
  refs.budgetLabel.textContent = `de ${formatBytes(policy.budgetBytes)} internos`;
  refs.budgetProgress.value = progressValue;
  refs.budgetProgress.textContent = formatPercentage(progressValue);
  refs.budgetPercentage.textContent = formatPercentage(policy.budgetPercentage);
  refs.artifactCount.textContent = String(summary.artifactCount);
  refs.publishedCount.textContent = `${summary.publishedArtifactCount} publicados`;
  refs.artifactSize.textContent = formatBytes(summary.artifactBytes);
  refs.sharedSize.textContent = formatBytes(summary.sharedBytes);
  const generated = new Date(stats.generatedAt);
  refs.generatedAt.textContent = Number.isNaN(generated.getTime())
    ? stats.generatedAt
    : dateFormatter.format(generated);
  refs.fileCount.textContent = `${summary.fileCount} archivos medidos`;

  renderBreakdown(refs.areaBreakdown, breakdown.areas);
  renderBreakdown(refs.typeBreakdown, breakdown.types);
  renderBreakdown(refs.componentBreakdown, breakdown.components);
  renderArtifacts(stats.artifacts);
  renderLargestFiles(stats.largestFiles);
  renderWarnings(stats.warnings ?? []);
}

function showError(error) {
  refs.loadError.hidden = false;
  refs.loadErrorMessage.textContent =
    window.location.protocol === "file:"
      ? "Abre BibliotecaWeb mediante un servidor HTTP local para leer data/stats.json."
      : error.message;
}

async function loadStats() {
  try {
    const response = await fetch(new URL("../data/stats.json", document.baseURI), {
      cache: "no-cache",
    });
    if (!response.ok) {
      throw new Error(`Las estadísticas respondieron con el estado ${response.status}.`);
    }
    const stats = await response.json();
    validateStats(stats);
    renderStats(stats);
  } catch (error) {
    showError(error instanceof Error ? error : new Error("Error desconocido."));
  }
}

loadStats();
