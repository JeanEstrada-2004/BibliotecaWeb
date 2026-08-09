import Reveal from "../../../vendor/reveal/6.0.1/dist/reveal.mjs";
import { initializePresentation, renderRuntimeError } from "./runtime.js";

const roots = Array.from(document.querySelectorAll("[data-presentation-root]"));

for (const root of roots) {
  initializePresentation(root, Reveal).catch((error) => {
    renderRuntimeError(root, error);
  });
}
