const institution = "Universidad de San Martín de Porres";

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  element.className = className;
  if (text) element.textContent = text;
  return element;
}

export function mountBrand({ root, brandData }) {
  const faculty = brandData.faculty || "Facultad de Ingeniería y Arquitectura";
  const school = brandData.school || "Escuela Profesional de Ingeniería de Computación y Sistemas";
  const course = brandData.course || "Presentación académica";
  const author = brandData.author || null;

  const overlay = createElement("aside", "pc-brand pc-brand--usmp");
  overlay.dataset.pcBrandOverlay = "usmp";
  overlay.setAttribute("aria-label", `${institution}. ${course}.`);

  const identity = createElement("div", "pc-brand__identity");
  const monogram = createElement("span", "pc-brand__monogram", "U");
  monogram.setAttribute("aria-hidden", "true");

  const wordmark = createElement("div", "pc-brand__wordmark");
  wordmark.append(
    createElement("strong", "pc-brand__acronym", "USMP"),
    createElement("span", "pc-brand__institution", institution),
  );
  identity.append(monogram, wordmark);

  const context = createElement("div", "pc-brand__context");
  context.append(
    createElement("strong", "pc-brand__course", course),
    createElement("span", "pc-brand__faculty", faculty),
    createElement("span", "pc-brand__school", school),
  );
  if (author) {
    context.append(createElement("span", "pc-brand__author", author));
  }

  const edge = createElement("span", "pc-brand__edge");
  edge.setAttribute("aria-hidden", "true");
  overlay.append(identity, context, edge);
  root.append(overlay);

  return {
    update({ chrome, slide }) {
      overlay.dataset.chrome = chrome;
      overlay.dataset.slideId = slide?.dataset.slideId || "";
      overlay.hidden = chrome === "none";
    },
    destroy() {
      overlay.remove();
    },
  };
}

export default mountBrand;
