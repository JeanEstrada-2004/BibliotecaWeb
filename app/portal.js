const state = {
  catalog: null,
  stats: null,
  statsError: null,
  query: "",
  type: "all",
};

const refs = {
  primaryNavList: document.querySelector("#primary-nav-list"),
  heroKicker: document.querySelector("#hero-kicker"),
  heroTitle: document.querySelector("#hero-title"),
  heroSummary: document.querySelector("#hero-summary"),
  metricArtifacts: document.querySelector("#metric-artifacts"),
  metricSecondaryLabel: document.querySelector("#metric-secondary-label"),
  metricSecondary: document.querySelector("#metric-secondary"),
  searchForm: document.querySelector("#search-form"),
  searchInput: document.querySelector("#search-input"),
  searchClear: document.querySelector("#search-clear"),
  typeFilters: document.querySelector("#type-filters"),
  storageSummary: document.querySelector("#storage-summary"),
  storageStatus: document.querySelector("[data-storage-status]"),
  storageTitle: document.querySelector("[data-storage-title]"),
  storageSize: document.querySelector("[data-storage-size]"),
  storageCount: document.querySelector("[data-storage-count]"),
  storageProgress: document.querySelector("[data-storage-progress]"),
  storagePercentage: document.querySelector("[data-storage-percentage]"),
  breadcrumb: document.querySelector("#breadcrumb"),
  areasSection: document.querySelector("#areas-section"),
  areaGrid: document.querySelector("#area-grid"),
  collectionsSection: document.querySelector("#collections-section"),
  collectionsTitle: document.querySelector("#collections-title"),
  collectionsSummary: document.querySelector("#collections-summary"),
  collectionGrid: document.querySelector("#collection-grid"),
  artifactsSection: document.querySelector("#artifacts-section"),
  artifactsTitle: document.querySelector("#artifacts-title"),
  resultsSummary: document.querySelector("#results-summary"),
  artifactGrid: document.querySelector("#artifact-grid"),
  loadError: document.querySelector("#load-error"),
  loadErrorMessage: document.querySelector("#load-error-message"),
  reloadButton: document.querySelector("#reload-button"),
  actionStatus: document.querySelector("#action-status"),
};

const dateFormatter = new Intl.DateTimeFormat("es-PE", {
  day: "numeric",
  month: "short",
  year: "numeric",
});

const sortByOrder = (first, second) =>
  (first.order ?? Number.MAX_SAFE_INTEGER) - (second.order ?? Number.MAX_SAFE_INTEGER) ||
  first.label.localeCompare(second.label, "es", { sensitivity: "base" });

function createElement(tagName, options = {}, children = []) {
  const element = document.createElement(tagName);

  if (options.className) {
    element.className = options.className;
  }

  if (options.text !== undefined) {
    element.textContent = options.text;
  }

  for (const [name, value] of Object.entries(options.attributes ?? {})) {
    if (value !== undefined && value !== null && value !== false) {
      element.setAttribute(name, value === true ? "" : String(value));
    }
  }

  for (const [name, value] of Object.entries(options.dataset ?? {})) {
    element.dataset[name] = value;
  }

  for (const child of children) {
    if (child) {
      element.append(child);
    }
  }

  return element;
}

function normalizeText(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .trim();
}

function pluralize(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural}`;
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
  return `${new Intl.NumberFormat("es-PE", { maximumFractionDigits: 1 }).format(value)} ${unit}`;
}

function collectionKey(areaId, collectionId) {
  return `${areaId}/${collectionId}`;
}

function artifactPath(artifact) {
  return `./artefactos/${artifact.areaId}/${artifact.collectionId}/${artifact.slug}/`;
}

function validateCatalog(catalog) {
  const requiredArrays = ["areas", "collections", "types", "artifacts"];

  if (!catalog || catalog.schemaVersion !== 1) {
    throw new Error("La versión del catálogo no es compatible.");
  }

  for (const property of requiredArrays) {
    if (!Array.isArray(catalog[property])) {
      throw new Error(`El catálogo no contiene una lista válida de ${property}.`);
    }
  }

  const areaIds = new Set(catalog.areas.map((area) => area.id));
  const typeIds = new Set(catalog.types.map((type) => type.id));
  const collectionIds = new Set(
    catalog.collections.map((collection) => collectionKey(collection.areaId, collection.id)),
  );

  if (areaIds.size !== catalog.areas.length || typeIds.size !== catalog.types.length) {
    throw new Error("El catálogo contiene identificadores duplicados.");
  }

  if (collectionIds.size !== catalog.collections.length) {
    throw new Error("El catálogo contiene colecciones duplicadas dentro de un área.");
  }

  for (const collection of catalog.collections) {
    if (!areaIds.has(collection.areaId)) {
      throw new Error(`La colección ${collection.id} pertenece a un área inexistente.`);
    }
  }

  const artifactIds = new Set();
  const artifactLocations = new Set();

  for (const artifact of catalog.artifacts) {
    const location = `${artifact.areaId}/${artifact.collectionId}/${artifact.slug}`;

    if (artifactIds.has(artifact.id) || artifactLocations.has(location)) {
      throw new Error(`El artefacto ${artifact.id} está duplicado.`);
    }

    if (!areaIds.has(artifact.areaId)) {
      throw new Error(`El artefacto ${artifact.id} usa un área inexistente.`);
    }

    if (!collectionIds.has(collectionKey(artifact.areaId, artifact.collectionId))) {
      throw new Error(`El artefacto ${artifact.id} usa una colección inexistente.`);
    }

    if (!typeIds.has(artifact.type)) {
      throw new Error(`El artefacto ${artifact.id} usa un tipo inexistente.`);
    }

    artifactIds.add(artifact.id);
    artifactLocations.add(location);
  }
}

function validateStats(stats) {
  if (!stats || stats.schemaVersion !== 1 || stats.scope !== "public-static-files") {
    throw new Error("La versión de las estadísticas no es compatible.");
  }
  if (!stats.summary || !stats.policy?.status) {
    throw new Error("El resumen de estadísticas está incompleto.");
  }
}

function prepareCatalog(catalog) {
  const areas = [...catalog.areas].sort(sortByOrder);
  const types = [...catalog.types].sort(sortByOrder);
  const collections = [...catalog.collections].sort(sortByOrder);
  const artifacts = [...catalog.artifacts];

  return {
    ...catalog,
    areas,
    types,
    collections,
    artifacts,
    publishedArtifacts: artifacts.filter((artifact) => artifact.status === "published"),
    areaById: new Map(areas.map((area) => [area.id, area])),
    typeById: new Map(types.map((type) => [type.id, type])),
    collectionByKey: new Map(
      collections.map((collection) => [collectionKey(collection.areaId, collection.id), collection]),
    ),
  };
}

function parseRoute() {
  const rawHash = window.location.hash.replace(/^#\/?/, "");

  if (!rawHash || rawHash === "inicio") {
    return { kind: "home", area: null, collection: null };
  }

  let segments;

  try {
    segments = rawHash
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
  } catch {
    return { kind: "not-found", area: null, collection: null };
  }

  if (segments.length < 1 || segments.length > 2) {
    return { kind: "not-found", area: null, collection: null };
  }

  const area = state.catalog.areaById.get(segments[0]);

  if (!area) {
    return { kind: "not-found", area: null, collection: null };
  }

  if (segments.length === 1) {
    return { kind: "area", area, collection: null };
  }

  const collection = state.catalog.collectionByKey.get(collectionKey(area.id, segments[1]));

  if (!collection) {
    return { kind: "not-found", area, collection: null };
  }

  return { kind: "collection", area, collection };
}

function artifactsForRoute(route) {
  if (route.kind === "not-found") {
    return [];
  }

  return state.catalog.publishedArtifacts.filter((artifact) => {
    if (route.area && artifact.areaId !== route.area.id) {
      return false;
    }

    return !route.collection || artifact.collectionId === route.collection.id;
  });
}

function artifactSearchText(artifact) {
  const area = state.catalog.areaById.get(artifact.areaId);
  const collection = state.catalog.collectionByKey.get(
    collectionKey(artifact.areaId, artifact.collectionId),
  );
  const type = state.catalog.typeById.get(artifact.type);

  return normalizeText(
    [
      artifact.title,
      artifact.summary,
      area?.label,
      collection?.label,
      type?.label,
      ...(artifact.tags ?? []),
    ].join(" "),
  );
}

function renderPrimaryNav(route) {
  const items = state.catalog.areas.map((area) => {
    const link = createElement("a", {
      text: area.label,
      attributes: {
        href: `#/${area.id}`,
        "aria-current": route.area?.id === area.id ? "page" : null,
      },
    });

    return createElement("li", {}, [link]);
  });

  refs.primaryNavList.replaceChildren(...items);
}

function renderHero(route) {
  const scopedArtifacts = artifactsForRoute(route);

  if (route.kind === "home") {
    refs.heroKicker.textContent = "Archivo personal de artefactos estáticos";
    refs.heroTitle.textContent = "Biblioteca Web";
    refs.heroSummary.textContent =
      "Un solo lugar para organizar presentaciones, mockups y páginas creadas para universidad, trabajo y proyectos personales.";
    refs.metricSecondaryLabel.textContent = "Áreas disponibles";
    refs.metricSecondary.textContent = String(state.catalog.areas.length);
    document.title = "Biblioteca Web";
  } else if (route.kind === "area") {
    const collectionCount = state.catalog.collections.filter(
      (collection) => collection.areaId === route.area.id,
    ).length;
    refs.heroKicker.textContent = "Área de la biblioteca";
    refs.heroTitle.textContent = route.area.label;
    refs.heroSummary.textContent = route.area.description;
    refs.metricSecondaryLabel.textContent = "Colecciones";
    refs.metricSecondary.textContent = String(collectionCount);
    document.title = `${route.area.label} · Biblioteca Web`;
  } else if (route.kind === "collection") {
    refs.heroKicker.textContent = route.area.label;
    refs.heroTitle.textContent = route.collection.label;
    refs.heroSummary.textContent =
      "Presentaciones y otros artefactos organizados dentro de esta colección.";
    refs.metricSecondaryLabel.textContent = "En esta colección";
    refs.metricSecondary.textContent = String(scopedArtifacts.length);
    document.title = `${route.collection.label} · Biblioteca Web`;
  } else {
    refs.heroKicker.textContent = "La ruta solicitada no existe";
    refs.heroTitle.textContent = "No encontramos esa sección";
    refs.heroSummary.textContent =
      "Regresa al inicio para continuar explorando las áreas disponibles de la biblioteca.";
    refs.metricSecondaryLabel.textContent = "Áreas disponibles";
    refs.metricSecondary.textContent = String(state.catalog.areas.length);
    document.title = "Sección no encontrada · Biblioteca Web";
  }

  refs.metricArtifacts.textContent = String(scopedArtifacts.length);
}

function renderBreadcrumb(route) {
  if (route.kind === "home") {
    refs.breadcrumb.hidden = true;
    refs.breadcrumb.replaceChildren();
    return;
  }

  const parts = [
    createElement("a", { text: "Inicio", attributes: { href: "#/inicio" } }),
    createElement("span", {
      className: "breadcrumb__separator",
      text: "/",
      attributes: { "aria-hidden": "true" },
    }),
  ];

  if (route.area) {
    if (route.collection) {
      parts.push(
        createElement("a", {
          text: route.area.label,
          attributes: { href: `#/${route.area.id}` },
        }),
        createElement("span", {
          className: "breadcrumb__separator",
          text: "/",
          attributes: { "aria-hidden": "true" },
        }),
        createElement("span", {
          text: route.collection.label,
          attributes: { "aria-current": "page" },
        }),
      );
    } else {
      parts.push(
        createElement("span", {
          text: route.area.label,
          attributes: { "aria-current": "page" },
        }),
      );
    }
  } else {
    parts.push(
      createElement("span", {
        text: "Sección no encontrada",
        attributes: { "aria-current": "page" },
      }),
    );
  }

  refs.breadcrumb.replaceChildren(...parts);
  refs.breadcrumb.hidden = false;
}

function renderStorageSummary(route) {
  refs.storageSummary.hidden = route.kind !== "home";
  if (route.kind !== "home") {
    return;
  }

  if (!state.stats) {
    refs.storageSummary.dataset.tone = state.statsError ? "unavailable" : "loading";
    refs.storageTitle.textContent = state.statsError
      ? "Resumen temporalmente no disponible"
      : "Calculando la huella actual…";
    refs.storageSize.textContent = "—";
    refs.storageCount.textContent = state.statsError ? "Consulta la página de estado" : "— artefactos";
    refs.storageProgress.value = 0;
    refs.storageProgress.textContent = "0%";
    refs.storagePercentage.textContent = "Política interna";
    return;
  }

  const { summary, policy } = state.stats;
  const percentage = Math.min(Math.max(policy.budgetPercentage, 0), 100);
  refs.storageSummary.dataset.tone = policy.status.tone;
  refs.storageTitle.textContent = `${policy.status.label}: ${policy.status.message}`;
  refs.storageSize.textContent = formatBytes(summary.totalBytes);
  refs.storageCount.textContent = pluralize(summary.artifactCount, "artefacto", "artefactos");
  refs.storageProgress.value = percentage;
  refs.storageProgress.textContent = `${percentage}%`;
  refs.storagePercentage.textContent = `${policy.budgetPercentage}% de la política interna`;
}

function createAreaCard(area) {
  const collections = state.catalog.collections.filter(
    (collection) => collection.areaId === area.id,
  );
  const artifactCount = state.catalog.publishedArtifacts.filter(
    (artifact) => artifact.areaId === area.id,
  ).length;

  const collectionLabels = collections.slice(0, 3).map((collection) =>
    createElement("span", { text: collection.shortLabel ?? collection.label }),
  );

  if (collections.length > 3) {
    collectionLabels.push(createElement("span", { text: `+${collections.length - 3} más` }));
  }

  if (collections.length === 0) {
    collectionLabels.push(createElement("span", { text: "Colecciones por definir" }));
  }

  const top = createElement("div", { className: "area-card__top" }, [
    createElement("span", {
      className: "area-card__number",
      text: String(area.order).padStart(2, "0"),
    }),
    createElement("span", {
      className: "count-pill",
      text: pluralize(artifactCount, "artefacto", "artefactos"),
    }),
  ]);

  return createElement(
    "article",
    { className: "area-card", dataset: { area: area.id } },
    [
      top,
      createElement("h3", { text: area.label }),
      createElement("p", { className: "area-card__description", text: area.description }),
      createElement("div", { className: "area-card__collections" }, collectionLabels),
      createElement("a", {
        className: "area-card__link",
        text: "Explorar área",
        attributes: { href: `#/${area.id}` },
      }),
    ],
  );
}

function renderAreas(route) {
  refs.areasSection.hidden = route.kind !== "home";

  if (route.kind === "home") {
    refs.areaGrid.replaceChildren(...state.catalog.areas.map(createAreaCard));
  } else {
    refs.areaGrid.replaceChildren();
  }
}

function createCollectionCard(collection, route) {
  const artifactCount = state.catalog.publishedArtifacts.filter(
    (artifact) =>
      artifact.areaId === collection.areaId && artifact.collectionId === collection.id,
  ).length;
  const isCurrent = route.collection?.id === collection.id;

  const card = createElement(
    "a",
    {
      className: "collection-card",
      attributes: {
        href: `#/${collection.areaId}/${collection.id}`,
        "aria-current": isCurrent ? "page" : null,
      },
      dataset: { area: collection.areaId },
    },
    [
      createElement("div", { className: "collection-card__top" }, [
        createElement("span", { className: "collection-card__marker" }),
        createElement("span", {
          className: "count-pill",
          text: pluralize(artifactCount, "artefacto", "artefactos"),
        }),
      ]),
      createElement("h3", { text: collection.label }),
      createElement("p", {
        className: "collection-card__meta",
        text: collection.description ?? "Colección de la biblioteca",
      }),
      createElement("span", {
        className: "collection-card__action",
        text: isCurrent ? "Colección actual" : "Ver colección →",
      }),
    ],
  );

  return card;
}

function renderCollections(route) {
  const shouldShow = route.kind === "area" || route.kind === "collection";
  refs.collectionsSection.hidden = !shouldShow;

  if (!shouldShow) {
    refs.collectionGrid.replaceChildren();
    return;
  }

  const collections = state.catalog.collections.filter(
    (collection) => collection.areaId === route.area.id,
  );

  refs.collectionsTitle.textContent = `Colecciones de ${route.area.label}`;
  refs.collectionsSummary.textContent = collections.length
    ? "Selecciona una colección para acotar el catálogo."
    : "Las colecciones de esta área se incorporarán cuando estén definidas.";

  if (collections.length === 0) {
    refs.collectionGrid.replaceChildren(
      createElement("p", {
        className: "empty-collection",
        text: "Esta área está preparada, pero aún no tiene colecciones registradas.",
      }),
    );
    return;
  }

  refs.collectionGrid.replaceChildren(
    ...collections.map((collection) => createCollectionCard(collection, route)),
  );
}

function renderTypeFilters(searchMatchedArtifacts) {
  const options = [{ id: "all", label: "Todos" }, ...state.catalog.types];
  const buttons = options.map((type) => {
    const count =
      type.id === "all"
        ? searchMatchedArtifacts.length
        : searchMatchedArtifacts.filter((artifact) => artifact.type === type.id).length;

    const countLabel = createElement("span", { text: String(count) });
    const button = createElement(
      "button",
      {
        className: "filter-button",
        text: type.label,
        attributes: {
          type: "button",
          "aria-pressed": state.type === type.id ? "true" : "false",
        },
        dataset: { type: type.id },
      },
      [countLabel],
    );

    button.addEventListener("click", () => {
      state.type = type.id;
      renderPortal();
    });

    return button;
  });

  refs.typeFilters.replaceChildren(...buttons);
}

function formatDate(value) {
  if (!value) {
    return "Sin fecha";
  }

  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

function createArtifactCard(artifact) {
  const area = state.catalog.areaById.get(artifact.areaId);
  const collection = state.catalog.collectionByKey.get(
    collectionKey(artifact.areaId, artifact.collectionId),
  );
  const type = state.catalog.typeById.get(artifact.type);
  const path = artifactPath(artifact);

  const cover = createElement("div", {
    className: "artifact-card__cover",
    dataset: { type: artifact.type },
  });

  if (artifact.cover) {
    cover.append(
      createElement("img", {
        attributes: {
          src: `${path}${artifact.cover}`,
          alt: "",
          loading: "lazy",
          decoding: "async",
        },
      }),
    );
  } else {
    cover.append(
      createElement("span", {
        className: "artifact-card__monogram",
        text: (type?.label ?? artifact.type).slice(0, 1),
        attributes: { "aria-hidden": "true" },
      }),
    );
  }

  const tags = (artifact.tags ?? [])
    .slice(0, 3)
    .map((tag) => createElement("li", { text: tag }));

  const copyButton = createElement("button", {
    className: "artifact-card__copy",
    text: "Copiar enlace",
    attributes: { type: "button" },
  });

  copyButton.addEventListener("click", async () => {
    const url = new URL(path, document.baseURI).href;
    const copied = await copyText(url);
    const originalText = "Copiar enlace";

    copyButton.textContent = copied ? "Copiado" : "No se pudo copiar";
    announce(copied ? `Enlace de ${artifact.title} copiado.` : "No se pudo copiar el enlace.");

    window.setTimeout(() => {
      copyButton.textContent = originalText;
    }, 1800);
  });

  const body = createElement("div", { className: "artifact-card__body" }, [
    createElement("div", { className: "artifact-card__context" }, [
      createElement("span", { text: type?.label ?? artifact.type }),
      createElement("time", {
        text: formatDate(artifact.publishedAt),
        attributes: { datetime: artifact.publishedAt },
      }),
    ]),
    createElement("h3", { text: artifact.title }),
    createElement("p", { className: "artifact-card__summary", text: artifact.summary }),
    tags.length ? createElement("ul", { className: "artifact-card__tags" }, tags) : null,
    createElement("div", { className: "artifact-card__actions" }, [
      createElement("a", {
        className: "artifact-card__open",
        text: "Abrir artefacto",
        attributes: { href: path },
      }),
      copyButton,
    ]),
  ]);

  const article = createElement("article", { className: "artifact-card" }, [cover, body]);
  article.setAttribute(
    "aria-label",
    `${artifact.title}, ${collection?.label ?? "colección"}, ${area?.label ?? "área"}`,
  );
  return article;
}

function createEmptyState(route, hasQuery) {
  let title = "Esta sección espera su primer artefacto";
  let message = "La estructura ya está preparada. Los contenidos se incorporarán en las siguientes etapas.";

  if (route.kind === "not-found") {
    title = "Esa sección no existe";
    message = "Comprueba la dirección o regresa al inicio para continuar explorando.";
  } else if (hasQuery) {
    title = "No encontramos coincidencias";
    message = "Prueba con otro término, elimina el filtro de tipo o explora una colección diferente.";
  } else if (state.type !== "all") {
    const type = state.catalog.typeById.get(state.type);
    const typePlurals = {
      presentation: "presentaciones",
      mockup: "mockups",
      page: "páginas",
    };
    title = `Aún no hay ${typePlurals[type?.id] ?? "artefactos de este tipo"} aquí`;
    message = "Selecciona otro tipo o vuelve más adelante cuando se publiquen nuevos artefactos.";
  }

  return createElement("div", { className: "empty-state" }, [
    createElement("div", { className: "empty-state__inner" }, [
      createElement("span", {
        className: "empty-state__symbol",
        text: "B",
        attributes: { "aria-hidden": "true" },
      }),
      createElement("h3", { text: title }),
      createElement("p", { text: message }),
    ]),
  ]);
}

function renderArtifacts(route) {
  const scopedArtifacts = artifactsForRoute(route);
  const normalizedQuery = normalizeText(state.query);
  const queryMatchedArtifacts = normalizedQuery
    ? scopedArtifacts.filter((artifact) => artifactSearchText(artifact).includes(normalizedQuery))
    : scopedArtifacts;

  renderTypeFilters(queryMatchedArtifacts);

  let filteredArtifacts = queryMatchedArtifacts.filter(
    (artifact) => state.type === "all" || artifact.type === state.type,
  );

  filteredArtifacts.sort((first, second) =>
    String(second.publishedAt ?? "").localeCompare(String(first.publishedAt ?? "")),
  );

  const isDefaultHome = route.kind === "home" && !normalizedQuery && state.type === "all";
  if (isDefaultHome) {
    filteredArtifacts = filteredArtifacts.slice(0, 6);
  }

  if (route.kind === "collection") {
    refs.artifactsTitle.textContent = `Artefactos de ${route.collection.label}`;
  } else if (route.kind === "area") {
    refs.artifactsTitle.textContent = `Artefactos de ${route.area.label}`;
  } else if (route.kind === "not-found") {
    refs.artifactsTitle.textContent = "Sección no encontrada";
  } else if (normalizedQuery || state.type !== "all") {
    refs.artifactsTitle.textContent = "Resultados de la biblioteca";
  } else {
    refs.artifactsTitle.textContent = "Publicaciones recientes";
  }

  refs.resultsSummary.textContent = pluralize(
    filteredArtifacts.length,
    "resultado visible",
    "resultados visibles",
  );

  const cards = filteredArtifacts.length
    ? filteredArtifacts.map(createArtifactCard)
    : [createEmptyState(route, Boolean(normalizedQuery))];

  refs.artifactGrid.replaceChildren(...cards);
  refs.artifactGrid.setAttribute("aria-busy", "false");
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Continúa con el fallback local.
    }
  }

  const textArea = createElement("textarea", {
    attributes: { readonly: true, "aria-hidden": "true" },
  });
  textArea.value = value;
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.append(textArea);
  textArea.select();

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  }

  textArea.remove();
  return copied;
}

function announce(message) {
  refs.actionStatus.textContent = "";
  window.setTimeout(() => {
    refs.actionStatus.textContent = message;
  }, 20);
}

function renderPortal() {
  if (!state.catalog) {
    return;
  }

  const route = parseRoute();
  renderPrimaryNav(route);
  renderHero(route);
  renderStorageSummary(route);
  renderBreadcrumb(route);
  renderAreas(route);
  renderCollections(route);
  renderArtifacts(route);
}

function showLoadError(error) {
  refs.loadError.hidden = false;
  refs.areasSection.hidden = true;
  refs.collectionsSection.hidden = true;
  refs.artifactsSection.hidden = true;
  refs.storageSummary.hidden = true;
  refs.searchInput.disabled = true;
  refs.heroKicker.textContent = "No se pudo cargar el catálogo";
  refs.heroTitle.textContent = "Biblioteca no disponible";
  refs.heroSummary.textContent =
    "La estructura del portal está lista, pero sus datos no pudieron leerse en este momento.";
  refs.metricArtifacts.textContent = "—";
  refs.metricSecondary.textContent = "—";
  refs.loadErrorMessage.textContent =
    window.location.protocol === "file:"
      ? "Abre el proyecto mediante un servidor HTTP local; el modo file:// no forma parte del entorno soportado."
      : error.message;
}

async function loadStats() {
  state.stats = null;
  state.statsError = null;
  try {
    const response = await fetch(new URL("./data/stats.json", document.baseURI), {
      cache: "no-cache",
    });
    if (!response.ok) {
      throw new Error(`Las estadísticas respondieron con el estado ${response.status}.`);
    }
    const stats = await response.json();
    validateStats(stats);
    state.stats = stats;
  } catch (error) {
    state.statsError = error instanceof Error ? error.message : "Error desconocido.";
  }
  renderPortal();
}

async function loadCatalog() {
  refs.loadError.hidden = true;
  refs.searchInput.disabled = false;
  refs.artifactsSection.hidden = false;
  refs.artifactGrid.setAttribute("aria-busy", "true");

  try {
    const response = await fetch(new URL("./data/catalog.json", document.baseURI), {
      cache: "no-cache",
    });

    if (!response.ok) {
      throw new Error(`El catálogo respondió con el estado ${response.status}.`);
    }

    const catalog = await response.json();
    validateCatalog(catalog);
    state.catalog = prepareCatalog(catalog);
    renderPortal();
    await loadStats();
  } catch (error) {
    showLoadError(error instanceof Error ? error : new Error("Error desconocido."));
  }
}

refs.searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
});

refs.searchInput.addEventListener("input", () => {
  state.query = refs.searchInput.value;
  refs.searchClear.hidden = state.query.length === 0;
  renderPortal();
});

refs.searchClear.addEventListener("click", () => {
  state.query = "";
  refs.searchInput.value = "";
  refs.searchClear.hidden = true;
  refs.searchInput.focus();
  renderPortal();
});

refs.reloadButton.addEventListener("click", () => {
  loadCatalog();
});

window.addEventListener("hashchange", () => {
  renderPortal();
  window.requestAnimationFrame(() => refs.heroTitle.focus({ preventScroll: true }));
});

refs.heroTitle.setAttribute("tabindex", "-1");
loadCatalog();
