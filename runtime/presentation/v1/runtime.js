const CONTRACT_VERSION = 1;
const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const TRANSITIONS = new Set(["none", "fade", "slide", "zoom"]);
const CHROME_LEVELS = new Set(["full", "minimal", "none"]);
const STEP_EFFECTS = new Set(["fade", "fade-up", "scale-in", "appear", "none"]);
const FEATURE_KEYS = [
  "controls",
  "progress",
  "slideNumber",
  "keyboard",
  "touch",
  "fullscreen",
];

class PresentationRuntimeError extends Error {
  constructor(message) {
    super(message);
    this.name = "PresentationRuntimeError";
  }
}

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function assert(condition, message) {
  if (!condition) {
    throw new PresentationRuntimeError(message);
  }
}

function assertOnlyKeys(record, allowedKeys, label) {
  const allowed = new Set(allowedKeys);
  const unexpected = Object.keys(record).filter((key) => !allowed.has(key));
  assert(
    unexpected.length === 0,
    `${label} contiene campos no soportados: ${unexpected.join(", ")}.`,
  );
}

function validateConfig(rawConfig) {
  assert(isRecord(rawConfig), "La configuración debe ser un objeto JSON.");
  assertOnlyKeys(
    rawConfig,
    [
      "contractVersion",
      "presentationId",
      "brand",
      "brandData",
      "homeHref",
      "aspectRatio",
      "chromeDefault",
      "transition",
      "features",
    ],
    "La configuración",
  );

  assert(
    rawConfig.contractVersion === CONTRACT_VERSION,
    `contractVersion debe ser ${CONTRACT_VERSION}.`,
  );
  assert(
    typeof rawConfig.presentationId === "string" &&
      SLUG_PATTERN.test(rawConfig.presentationId),
    "presentationId debe ser un slug ASCII válido.",
  );
  assert(
    rawConfig.brand === undefined ||
      rawConfig.brand === null ||
      (typeof rawConfig.brand === "string" && SLUG_PATTERN.test(rawConfig.brand)),
    "brand debe ser null o un slug ASCII válido.",
  );
  const rawBrandData = rawConfig.brandData ?? {};
  assert(isRecord(rawBrandData), "brandData debe ser un objeto.");
  const brandData = {};
  for (const [key, value] of Object.entries(rawBrandData)) {
    assert(/^[a-z][a-zA-Z0-9]*$/.test(key), `La clave brandData.${key} no es válida.`);
    assert(
      value === null || (typeof value === "string" && value.length <= 160),
      `brandData.${key} debe ser null o un texto de hasta 160 caracteres.`,
    );
    brandData[key] = typeof value === "string" ? value.trim() : null;
  }
  assert(
    rawConfig.brand !== null && rawConfig.brand !== undefined || Object.keys(brandData).length === 0,
    "brandData requiere un brand declarado.",
  );
  const homeHref = rawConfig.homeHref ?? "../../../../";
  const homeHasProtocol = /^[a-z][a-z\d+.-]*:/i.test(homeHref);
  assert(
    typeof homeHref === "string" &&
      homeHref.trim() === homeHref &&
      homeHref.length > 0 &&
      homeHref.length <= 256 &&
      !homeHref.startsWith("/") &&
      !homeHref.startsWith("\\") &&
      !homeHasProtocol &&
      !homeHref.includes("?") &&
      !homeHref.includes("#"),
    "homeHref debe ser una ruta local relativa de hasta 256 caracteres.",
  );
  assert(rawConfig.aspectRatio === "16:9", 'aspectRatio debe ser "16:9".');
  assert(
    CHROME_LEVELS.has(rawConfig.chromeDefault),
    "chromeDefault no pertenece al contrato V1.",
  );

  assert(isRecord(rawConfig.transition), "transition debe ser un objeto.");
  assertOnlyKeys(rawConfig.transition, ["default", "durationMs"], "transition");
  assert(
    TRANSITIONS.has(rawConfig.transition.default),
    "transition.default no pertenece al contrato V1.",
  );
  assert(
    Number.isInteger(rawConfig.transition.durationMs) &&
      rawConfig.transition.durationMs >= 0 &&
      rawConfig.transition.durationMs <= 3000,
    "transition.durationMs debe ser un entero entre 0 y 3000.",
  );

  assert(isRecord(rawConfig.features), "features debe ser un objeto.");
  assertOnlyKeys(rawConfig.features, FEATURE_KEYS, "features");
  for (const key of FEATURE_KEYS) {
    assert(
      typeof rawConfig.features[key] === "boolean",
      `features.${key} debe ser booleano.`,
    );
  }

  return {
    contractVersion: CONTRACT_VERSION,
    presentationId: rawConfig.presentationId,
    brand: rawConfig.brand ?? null,
    brandData,
    homeHref,
    aspectRatio: "16:9",
    chromeDefault: rawConfig.chromeDefault,
    transition: {
      default: rawConfig.transition.default,
      durationMs: rawConfig.transition.durationMs,
    },
    features: Object.fromEntries(
      FEATURE_KEYS.map((key) => [key, rawConfig.features[key]]),
    ),
  };
}

function resolveConfigUrl(root) {
  const configPath = root.dataset.presentationConfig || "presentation.config.json";
  const segments = configPath.split(/[\\/]/);
  const hasProtocol = /^[a-z][a-z\d+.-]*:/i.test(configPath);

  assert(configPath.trim() === configPath && configPath.length > 0, "La ruta de configuración no es válida.");
  assert(!configPath.startsWith("/") && !configPath.startsWith("\\"), "La configuración debe usar una ruta relativa.");
  assert(!hasProtocol && !segments.includes(".."), "La configuración debe permanecer dentro del artefacto.");

  return new URL(configPath, document.baseURI);
}

async function loadConfig(root) {
  const configUrl = resolveConfigUrl(root);
  const response = await fetch(configUrl, { cache: "no-cache" });

  assert(response.ok, `No se pudo cargar ${configUrl.pathname} (${response.status}).`);

  let rawConfig;
  try {
    rawConfig = await response.json();
  } catch {
    throw new PresentationRuntimeError("presentation.config.json no contiene JSON válido.");
  }

  return validateConfig(rawConfig);
}

async function loadBrandStylesheet(brandId) {
  const styleUrl = new URL(`../../../brands/${brandId}/brand.css`, import.meta.url);
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = styleUrl.href;
  link.dataset.pcBrandStyle = brandId;

  const loaded = new Promise((resolve, reject) => {
    link.addEventListener("load", resolve, { once: true });
    link.addEventListener(
      "error",
      () => reject(new PresentationRuntimeError(`No se pudo cargar el CSS del brand "${brandId}".`)),
      { once: true },
    );
  });

  document.head.append(link);
  await loaded;
  return link;
}

async function loadBrand(root, config) {
  if (!config.brand) return null;

  const brandId = config.brand;
  const scriptUrl = new URL(`../../../brands/${brandId}/brand.js`, import.meta.url);
  let styleLink;

  try {
    styleLink = await loadBrandStylesheet(brandId);
    const brandModule = await import(scriptUrl.href);
    const mountBrand = brandModule.mountBrand ?? brandModule.default;
    assert(typeof mountBrand === "function", `El brand "${brandId}" no expone mountBrand().`);

    const instance = mountBrand({
      root,
      brandId,
      brandData: { ...config.brandData },
    });
    assert(isRecord(instance), `El brand "${brandId}" no devolvió un controlador válido.`);
    assert(typeof instance.update === "function", `El brand "${brandId}" no implementa update().`);

    root.dataset.pcBrand = brandId;
    return {
      update: instance.update,
      destroy() {
        instance.destroy?.();
        styleLink.remove();
        delete root.dataset.pcBrand;
      },
    };
  } catch (error) {
    styleLink?.remove();
    throw error;
  }
}

function normalizeSlides(root, config) {
  const slidesContainer = Array.from(root.children).find((element) =>
    element.classList.contains("slides"),
  );
  assert(slidesContainer, 'La presentación necesita un contenedor directo con class="slides".');

  const slides = Array.from(slidesContainer.children);
  assert(slides.length > 0, "La presentación necesita al menos una diapositiva.");
  assert(
    slides.every((slide) => slide.matches("section[data-slide]")),
    "Cada hijo directo de .slides debe ser un section[data-slide].",
  );

  const slideIds = new Set();

  slides.forEach((slide) => {
    const slideId = slide.dataset.slideId;
    assert(slideId && SLUG_PATTERN.test(slideId), "Cada slide necesita un data-slide-id válido.");
    assert(!slideIds.has(slideId), `El data-slide-id "${slideId}" está duplicado.`);
    slideIds.add(slideId);

    assert(!slide.id || slide.id === slideId, `El id HTML de "${slideId}" debe coincidir con data-slide-id.`);
    slide.id = slideId;
    slide.classList.add("pc-slide");

    const transition = slide.dataset.transition || config.transition.default;
    assert(TRANSITIONS.has(transition), `La transición "${transition}" no pertenece al contrato V1.`);
    slide.dataset.transition = transition;

    const chromeLevel = slide.dataset.brandChrome || config.chromeDefault;
    assert(CHROME_LEVELS.has(chromeLevel), `El chrome "${chromeLevel}" no pertenece al contrato V1.`);
    slide.dataset.brandChrome = chromeLevel;

    const stepIds = new Set();
    let nextAutomaticIndex = 0;

    slide.querySelectorAll("[data-step]").forEach((step) => {
      const stepId = step.dataset.stepId;
      const effect = step.dataset.stepEffect || "fade";
      const explicitIndex = step.dataset.stepIndex;

      assert(stepId && SLUG_PATTERN.test(stepId), `Un step de "${slideId}" no tiene data-step-id válido.`);
      assert(!stepIds.has(stepId), `El data-step-id "${stepId}" está duplicado en "${slideId}".`);
      assert(STEP_EFFECTS.has(effect), `El efecto de step "${effect}" no pertenece al contrato V1.`);

      let fragmentIndex = nextAutomaticIndex;
      if (explicitIndex !== undefined) {
        fragmentIndex = Number(explicitIndex);
        assert(
          Number.isInteger(fragmentIndex) && fragmentIndex >= 0,
          `data-step-index de "${stepId}" debe ser un entero no negativo.`,
        );
      }

      nextAutomaticIndex = Math.max(nextAutomaticIndex, fragmentIndex + 1);
      stepIds.add(stepId);
      step.dataset.fragmentIndex = String(fragmentIndex);
      step.classList.add("fragment", "custom", "pc-step", `pc-step--${effect}`);
    });
  });

  return slides;
}

function getTransitionSpeed(durationMs) {
  if (durationMs <= 400) return "fast";
  if (durationMs >= 1000) return "slow";
  return "default";
}

function createRevealOptions(config, reducedMotion) {
  const transition = reducedMotion ? "none" : config.transition.default;

  return {
    width: 1600,
    height: 900,
    margin: 0,
    minScale: 0.12,
    maxScale: 2,
    center: false,
    hash: true,
    respondToHashChanges: true,
    controls: config.features.controls,
    controlsTutorial: false,
    progress: config.features.progress,
    slideNumber: config.features.slideNumber ? "c/t" : false,
    keyboard: config.features.keyboard,
    touch: config.features.touch,
    navigationMode: "linear",
    jumpToSlide: false,
    overview: false,
    transition,
    backgroundTransition: transition === "none" ? "none" : "fade",
    transitionSpeed: getTransitionSpeed(config.transition.durationMs),
    autoAnimate: false,
  };
}

function makeState(deck, slides, config) {
  const currentSlide = deck.getCurrentSlide() || slides[0];
  const slideIndex = Math.max(0, slides.indexOf(currentSlide));
  const allSteps = Array.from(currentSlide.querySelectorAll(".pc-step"));
  const visibleSteps = allSteps.filter((step) => step.classList.contains("visible"));
  const distinctStepIndexes = new Set(
    allSteps.map((step) => Number(step.dataset.fragmentIndex)),
  );
  const currentStepIndex = visibleSteps.length
    ? Math.max(...visibleSteps.map((step) => Number(step.dataset.fragmentIndex)))
    : -1;

  return {
    presentationId: config.presentationId,
    slideId: currentSlide.dataset.slideId,
    slideIndex,
    slideCount: slides.length,
    stepIndex: currentStepIndex,
    stepCount: distinctStepIndexes.size,
    activeStepIds: visibleSteps.map((step) => step.dataset.stepId),
  };
}

function directionBetween(previous, current) {
  if (!previous) return "none";
  if (current.slideIndex > previous.slideIndex) return "next";
  if (current.slideIndex < previous.slideIndex) return "previous";
  if (current.stepIndex > previous.stepIndex) return "next";
  if (current.stepIndex < previous.stepIndex) return "previous";
  return "none";
}

function statesMatch(first, second) {
  return (
    first?.slideId === second?.slideId &&
    first?.stepIndex === second?.stepIndex &&
    first?.activeStepIds.join("|") === second?.activeStepIds.join("|")
  );
}

function dispatch(root, eventName, detail) {
  root.dispatchEvent(new CustomEvent(eventName, { detail }));
}

function isEditableTarget(target) {
  return target instanceof Element && Boolean(target.closest("input, textarea, select, button, [contenteditable]"));
}

function createFullscreenControl(root, enabled) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pc-fullscreen-control";
  button.dataset.pcRuntimeControl = "fullscreen";

  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "⛶";
  button.append(icon);

  const supported = enabled && document.fullscreenEnabled && typeof root.requestFullscreen === "function";
  button.hidden = !supported;
  root.append(button);

  return { button, supported };
}

function createHomeControl(root, homeHref) {
  const link = document.createElement("a");
  link.className = "pc-home-control";
  link.dataset.pcRuntimeControl = "home";
  link.href = new URL(homeHref, document.baseURI).href;
  link.setAttribute("aria-label", "Volver a BibliotecaWeb");
  link.title = "Volver a BibliotecaWeb";

  const icon = document.createElement("span");
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = "←";
  const label = document.createElement("span");
  label.textContent = "Biblioteca";
  link.append(icon, label);
  root.append(link);
  return link;
}

function createController(root, deck, slides, config, motionQuery, brandController) {
  let destroyed = false;
  let lastState = null;
  let stepChangeQueued = false;
  const home = createHomeControl(root, config.homeHref);
  const fullscreen = createFullscreenControl(root, config.features.fullscreen);

  const currentState = () => makeState(deck, slides, config);

  function updateChrome(state) {
    const slide = slides[state.slideIndex];
    const chrome = slide?.dataset.brandChrome || config.chromeDefault;
    root.dataset.pcChrome = chrome;
    brandController?.update({
      chrome,
      slide,
      state: { ...state, activeStepIds: [...state.activeStepIds] },
    });
  }

  function updateFullscreenState() {
    const active = document.fullscreenElement === root;
    root.classList.toggle("pc-is-fullscreen", active);
    fullscreen.button.setAttribute("aria-pressed", String(active));
    fullscreen.button.setAttribute(
      "aria-label",
      active ? "Salir de pantalla completa" : "Entrar en pantalla completa",
    );
    fullscreen.button.title = active ? "Salir de pantalla completa (F)" : "Pantalla completa (F)";
  }

  async function toggleFullscreen() {
    if (!fullscreen.supported) return false;

    try {
      if (document.fullscreenElement === root) {
        await document.exitFullscreen();
      } else {
        await root.requestFullscreen();
      }
      return true;
    } catch (error) {
      root.dataset.pcFullscreenError = "true";
      console.error("No se pudo cambiar el modo pantalla completa.", error);
      return false;
    }
  }

  function emitStepChange() {
    stepChangeQueued = false;
    if (destroyed) return;

    const nextState = currentState();
    if (statesMatch(lastState, nextState)) return;

    const previousState = lastState;
    const direction = directionBetween(previousState, nextState);
    lastState = nextState;
    dispatch(root, "pc:stepchange", {
      previous: previousState,
      current: nextState,
      direction,
    });
  }

  function queueStepChange() {
    if (stepChangeQueued) return;
    stepChangeQueued = true;
    queueMicrotask(emitStepChange);
  }

  function onSlideChanged() {
    const nextState = currentState();
    const previousState = lastState;
    const direction = directionBetween(previousState, nextState);

    if (previousState) {
      dispatch(root, "pc:slideleave", {
        previous: previousState,
        current: nextState,
        direction,
      });
    }

    lastState = nextState;
    updateChrome(nextState);
    dispatch(root, "pc:slideenter", {
      previous: previousState,
      current: nextState,
      direction,
    });
  }

  function onResize() {
    dispatch(root, "pc:resize", {
      current: currentState(),
      scale: deck.getScale(),
    });
  }

  function onMotionPreferenceChanged(event) {
    root.dataset.pcReducedMotion = String(event.matches);
    deck.configure({
      transition: event.matches ? "none" : config.transition.default,
      backgroundTransition: event.matches ? "none" : "fade",
    });
  }

  function onKeydown(event) {
    if (
      !config.features.keyboard ||
      !config.features.fullscreen ||
      event.defaultPrevented ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.key.toLowerCase() !== "f" ||
      isEditableTarget(event.target)
    ) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    toggleFullscreen();
  }

  const revealListeners = [
    ["slidechanged", onSlideChanged],
    ["fragmentshown", queueStepChange],
    ["fragmenthidden", queueStepChange],
    ["resize", onResize],
  ];

  revealListeners.forEach(([name, listener]) => deck.on(name, listener));
  fullscreen.button.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", updateFullscreenState);
  document.addEventListener("keydown", onKeydown, true);
  motionQuery.addEventListener("change", onMotionPreferenceChanged);
  updateFullscreenState();

  const api = {
    next: () => deck.next(),
    previous: () => deck.prev(),
    goTo(slideId, stepIndex = -1) {
      const index = slides.findIndex((slide) => slide.dataset.slideId === slideId);
      assert(index >= 0, `No existe el slide "${slideId}".`);
      assert(Number.isInteger(stepIndex) && stepIndex >= -1, "stepIndex debe ser un entero mayor o igual a -1.");
      deck.slide(index, 0, stepIndex);
    },
    getState() {
      const state = currentState();
      return { ...state, activeStepIds: [...state.activeStepIds] };
    },
    toggleFullscreen,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      const state = currentState();

      revealListeners.forEach(([name, listener]) => deck.off(name, listener));
      fullscreen.button.removeEventListener("click", toggleFullscreen);
      document.removeEventListener("fullscreenchange", updateFullscreenState);
      document.removeEventListener("keydown", onKeydown, true);
      motionQuery.removeEventListener("change", onMotionPreferenceChanged);
      home.remove();
      fullscreen.button.remove();
      brandController?.destroy();
      deck.destroy();
      delete root.pcPresentation;
      dispatch(root, "pc:destroy", { previous: state, current: null, direction: "none" });
    },
  };

  return {
    api,
    markReady() {
      lastState = currentState();
      updateChrome(lastState);
      root.dataset.pcReady = "true";
      root.pcPresentation = api;
      dispatch(root, "pc:ready", {
        previous: null,
        current: lastState,
        direction: "none",
        config,
      });
    },
  };
}

export async function initializePresentation(root, RevealConstructor) {
  assert(root instanceof HTMLElement, "No se encontró la raíz de la presentación.");
  assert(typeof RevealConstructor === "function", "El motor interno no está disponible.");

  const config = await loadConfig(root);
  const slides = normalizeSlides(root, config);
  const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

  root.classList.add("pc-presentation");
  root.dataset.pcContractVersion = String(CONTRACT_VERSION);
  root.dataset.pcPresentationId = config.presentationId;
  root.dataset.pcReducedMotion = String(motionQuery.matches);
  root.style.setProperty("--pc-transition-duration", `${config.transition.durationMs}ms`);

  const brandController = await loadBrand(root, config);
  const deck = new RevealConstructor(root, createRevealOptions(config, motionQuery.matches));
  const controller = createController(
    root,
    deck,
    slides,
    config,
    motionQuery,
    brandController,
  );

  await deck.initialize();
  controller.markReady();
  return controller.api;
}

export function renderRuntimeError(root, error) {
  root.dataset.pcRuntimeError = "true";

  const panel = document.createElement("section");
  panel.className = "pc-runtime-error";
  panel.setAttribute("role", "alert");

  const title = document.createElement("h1");
  title.textContent = "No se pudo iniciar la presentación";

  const message = document.createElement("p");
  message.textContent = error instanceof Error ? error.message : "Ocurrió un error inesperado.";

  panel.append(title, message);
  root.replaceChildren(panel);
  console.error(error);
}

export { PresentationRuntimeError };
