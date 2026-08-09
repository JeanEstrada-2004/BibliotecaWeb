(() => {
  "use strict";

  const COLORS = ["#7a1e3b", "#b8935f", "#4f1126", "#c98ba3", "#4f7358", "#3e5c76", "#8c6e4a"];
  const FIELD_DEFS = [
    { key: "timestamp", index: 0, keywords: ["marca temporal"] },
    { key: "edad", index: 1, keywords: ["rango de edad"] },
    { key: "escuela", index: 2, keywords: ["escuela academica"] },
    { key: "ciclo", index: 3, keywords: ["ciclo academico"] },
    { key: "ocupacion", index: 4, keywords: ["ocupacion principal"] },
    { key: "herramientas", index: 5, keywords: ["herramientas de inteligencia artificial utilizas"] },
    { key: "frecuencia", index: 6, keywords: ["con que frecuencia"] },
    { key: "paraque", index: 7, keywords: ["para que utilizas", "actividades o tareas apoyas", "apoyas principalmente el uso"] },
    { key: "likertAprend", index: 8, keywords: ["facilita mi aprendizaje academico"] },
    { key: "beneficio", index: 9, keywords: ["principal beneficio"] },
    { key: "riesgo", index: 10, keywords: ["riesgo consideras mas importante", "mayor riesgo derivado", "riesgo derivado del uso masivo", "percibes como el mayor riesgo"] },
    { key: "etico", index: 11, keywords: ["consideras etico presentar"] },
    { key: "confiable", index: 12, keywords: ["tan confiable"] },
    { key: "noReemplaza", index: 13, keywords: ["aun no puede reemplazar", "requiere necesariamente de la participacion humana", "participacion humana para garantizar"] },
    { key: "rol", index: 14, keywords: ["papel de la inteligencia artificial"] },
    { key: "fortalecer", index: 15, keywords: ["deberia fortalecerse"] },
    { key: "opinion", index: 16, keywords: ["alguna otra opinion"] }
  ];

  const charts = new Map();
  let pendingDestination = null;

  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .trim();
  }

  function truncate(value, maximum = 34) {
    const text = String(value || "").trim();
    return text.length > maximum ? `${text.slice(0, maximum - 1)}…` : text;
  }

  function findZipDirectory(bytes) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const earliestOffset = Math.max(0, bytes.length - 65557);

    for (let offset = bytes.length - 22; offset >= earliestOffset; offset -= 1) {
      if (view.getUint32(offset, true) === 0x06054b50) {
        return {
          entryCount: view.getUint16(offset + 10, true),
          directoryOffset: view.getUint32(offset + 16, true)
        };
      }
    }

    throw new Error("El archivo no tiene una estructura .xlsx válida.");
  }

  function readZipEntries(buffer) {
    const bytes = new Uint8Array(buffer);
    const view = new DataView(buffer);
    const decoder = new TextDecoder("utf-8");
    const { entryCount, directoryOffset } = findZipDirectory(bytes);
    const entries = new Map();
    let offset = directoryOffset;

    for (let index = 0; index < entryCount; index += 1) {
      if (view.getUint32(offset, true) !== 0x02014b50) {
        throw new Error("No se pudo leer el contenido interno del Excel.");
      }

      const flags = view.getUint16(offset + 8, true);
      const method = view.getUint16(offset + 10, true);
      const compressedSize = view.getUint32(offset + 20, true);
      const uncompressedSize = view.getUint32(offset + 24, true);
      const nameLength = view.getUint16(offset + 28, true);
      const extraLength = view.getUint16(offset + 30, true);
      const commentLength = view.getUint16(offset + 32, true);
      const localOffset = view.getUint32(offset + 42, true);
      const nameStart = offset + 46;
      const name = decoder.decode(bytes.subarray(nameStart, nameStart + nameLength));

      entries.set(name, { flags, method, compressedSize, uncompressedSize, localOffset });
      offset = nameStart + nameLength + extraLength + commentLength;
    }

    return { bytes, entries };
  }

  async function extractZipEntry(archive, name) {
    const entry = archive.entries.get(name);
    if (!entry) return null;
    if (entry.flags & 1) throw new Error("El Excel está cifrado y no puede procesarse.");

    const view = new DataView(archive.bytes.buffer, archive.bytes.byteOffset, archive.bytes.byteLength);
    if (view.getUint32(entry.localOffset, true) !== 0x04034b50) {
      throw new Error("Una sección interna del Excel está dañada.");
    }

    const nameLength = view.getUint16(entry.localOffset + 26, true);
    const extraLength = view.getUint16(entry.localOffset + 28, true);
    const dataStart = entry.localOffset + 30 + nameLength + extraLength;
    const compressed = archive.bytes.slice(dataStart, dataStart + entry.compressedSize);

    if (entry.method === 0) return compressed;
    if (entry.method !== 8) throw new Error("El Excel usa una compresión no compatible.");
    if (!("DecompressionStream" in window)) {
      throw new Error("Este navegador no puede descomprimir archivos .xlsx. Usa una versión reciente de Chrome o Edge.");
    }

    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    const uncompressed = new Uint8Array(await new Response(stream).arrayBuffer());
    if (entry.uncompressedSize && uncompressed.length !== entry.uncompressedSize) {
      throw new Error("Una sección interna del Excel está incompleta.");
    }
    return uncompressed;
  }

  function parseXml(bytes, label) {
    const xml = new DOMParser().parseFromString(new TextDecoder("utf-8").decode(bytes), "application/xml");
    if (xml.getElementsByTagName("parsererror").length) {
      throw new Error(`No se pudo interpretar ${label} del Excel.`);
    }
    return xml;
  }

  function elementsByName(parent, localName) {
    return Array.from(parent.getElementsByTagNameNS("*", localName));
  }

  function parseSharedStrings(bytes) {
    if (!bytes) return [];
    const xml = parseXml(bytes, "los textos");
    return elementsByName(xml, "si").map((item) =>
      elementsByName(item, "t").map((text) => text.textContent || "").join("")
    );
  }

  function columnIndex(reference) {
    const letters = String(reference || "").match(/^[A-Z]+/i)?.[0]?.toUpperCase() || "A";
    return [...letters].reduce((result, letter) => result * 26 + letter.charCodeAt(0) - 64, 0) - 1;
  }

  function cellValue(cell, sharedStrings) {
    const type = cell.getAttribute("t");
    if (type === "inlineStr") {
      return elementsByName(cell, "t").map((text) => text.textContent || "").join("");
    }

    const raw = elementsByName(cell, "v")[0]?.textContent || "";
    if (type === "s") return sharedStrings[Number(raw)] ?? "";
    if (type === "b") return raw === "1" ? "Sí" : "No";
    return raw;
  }

  function parseWorksheet(bytes, sharedStrings) {
    const xml = parseXml(bytes, "la hoja de respuestas");
    const matrix = [];

    elementsByName(xml, "row").forEach((rowElement, sequentialIndex) => {
      const declaredRow = Number(rowElement.getAttribute("r"));
      const rowIndex = Number.isInteger(declaredRow) && declaredRow > 0 ? declaredRow - 1 : sequentialIndex;
      const row = [];

      elementsByName(rowElement, "c").forEach((cell, cellIndex) => {
        const reference = cell.getAttribute("r");
        row[reference ? columnIndex(reference) : cellIndex] = cellValue(cell, sharedStrings);
      });
      matrix[rowIndex] = row;
    });

    const headerIndex = matrix.findIndex((row) => row?.some((value) => String(value || "").trim()));
    if (headerIndex === -1) throw new Error("El archivo no contiene encabezados ni respuestas.");

    const headers = matrix[headerIndex].map((value, index) => String(value || "").trim() || `Columna ${index + 1}`);
    const rows = matrix
      .slice(headerIndex + 1)
      .filter((row) => row?.some((value) => String(value ?? "").trim()))
      .map((row) => Object.fromEntries(headers.map((header, index) => [header, row?.[index] ?? ""])));

    return { rows, headers };
  }

  async function parseXlsx(buffer) {
    const archive = readZipEntries(buffer);
    const worksheetName = [...archive.entries.keys()]
      .filter((name) => /^xl\/worksheets\/sheet\d+\.xml$/i.test(name))
      .sort((first, second) => first.localeCompare(second, undefined, { numeric: true }))[0];

    if (!worksheetName) throw new Error("No se encontró una hoja de respuestas en el Excel.");

    const [worksheetBytes, sharedStringBytes] = await Promise.all([
      extractZipEntry(archive, worksheetName),
      extractZipEntry(archive, "xl/sharedStrings.xml")
    ]);
    const sharedStrings = parseSharedStrings(sharedStringBytes);
    return parseWorksheet(worksheetBytes, sharedStrings);
  }

  function resolveColumns(headers) {
    const normalizedHeaders = headers.map(normalizeText);
    const usedIndexes = new Set();
    const columns = {};

    FIELD_DEFS.forEach((definition) => {
      let matchedIndex = -1;

      for (const keyword of definition.keywords) {
        const normalizedKeyword = normalizeText(keyword);
        matchedIndex = normalizedHeaders.findIndex(
          (header, index) => header.includes(normalizedKeyword) && !usedIndexes.has(index)
        );
        if (matchedIndex !== -1) break;
      }

      if (matchedIndex === -1 && headers[definition.index] !== undefined && !usedIndexes.has(definition.index)) {
        matchedIndex = definition.index;
      }

      if (matchedIndex !== -1) usedIndexes.add(matchedIndex);
      columns[definition.key] = matchedIndex === -1 ? null : headers[matchedIndex];
    });

    return columns;
  }

  function countSingle(rows, column) {
    const counts = {};
    if (!column) return counts;

    rows.forEach((row) => {
      const value = String(row[column] ?? "").trim();
      if (!value) return;
      counts[value] = (counts[value] || 0) + 1;
    });
    return counts;
  }

  function countMultiple(rows, column) {
    const counts = {};
    if (!column) return counts;

    rows.forEach((row) => {
      const value = String(row[column] ?? "").trim();
      if (!value) return;

      value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => {
          counts[item] = (counts[item] || 0) + 1;
        });
    });
    return counts;
  }

  function averageNumeric(rows, column) {
    if (!column) return null;
    const values = rows
      .map((row) => String(row[column] ?? "").replace(",", ".").match(/-?\d+(?:\.\d+)?/))
      .filter(Boolean)
      .map((match) => Number(match[0]))
      .filter(Number.isFinite);

    if (!values.length) return null;
    return values.reduce((total, value) => total + value, 0) / values.length;
  }

  function topEntries(counts, limit = 7) {
    return Object.entries(counts)
      .sort((first, second) => second[1] - first[1])
      .slice(0, limit);
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  }

  function destroyCharts() {
    charts.forEach((chart) => chart.destroy());
    charts.clear();
  }

  function tooltipTitle(items) {
    return items[0]?.label || "";
  }

  function createBarChart(id, entries, horizontal = false) {
    const canvas = document.getElementById(id);
    if (!canvas || !entries.length) return;

    const chart = new window.Chart(canvas, {
      type: "bar",
      data: {
        labels: entries.map(([label]) => label),
        datasets: [{
          data: entries.map(([, value]) => value),
          backgroundColor: entries.map((_, index) => COLORS[index % COLORS.length]),
          borderRadius: 5,
          maxBarThickness: 38
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        indexAxis: horizontal ? "y" : "x",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: tooltipTitle } }
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: "rgba(122, 30, 59, 0.08)" },
            ticks: {
              color: "#6b5f5a",
              precision: 0,
              font: { size: 13, weight: "600" },
              callback(value) {
                return horizontal ? value : truncate(this.getLabelForValue(value), 18);
              }
            }
          },
          y: {
            beginAtZero: true,
            grid: { display: !horizontal, color: "rgba(122, 30, 59, 0.08)" },
            ticks: {
              color: "#6b5f5a",
              precision: 0,
              font: { size: 13, weight: "600" },
              callback(value) {
                return horizontal ? truncate(this.getLabelForValue(value), 30) : value;
              }
            }
          }
        }
      }
    });

    charts.set(id, chart);
  }

  function createDoughnutChart(id, entries) {
    const canvas = document.getElementById(id);
    if (!canvas || !entries.length) return;

    const chart = new window.Chart(canvas, {
      type: "doughnut",
      data: {
        labels: entries.map(([label]) => label),
        datasets: [{
          data: entries.map(([, value]) => value),
          backgroundColor: entries.map((_, index) => COLORS[index % COLORS.length]),
          borderColor: "#fffdf8",
          borderWidth: 3,
          hoverOffset: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        cutout: "58%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              boxWidth: 12,
              boxHeight: 12,
              padding: 13,
              color: "#6b5f5a",
              font: { size: 13, weight: "600" },
              generateLabels(chart) {
                const labels = window.Chart.defaults.plugins.legend.labels.generateLabels(chart);
                return labels.map((label) => ({ ...label, text: truncate(label.text, 34) }));
              }
            }
          },
          tooltip: { callbacks: { title: tooltipTitle } }
        }
      }
    });

    charts.set(id, chart);
  }

  function resizeCharts() {
    window.requestAnimationFrame(() => {
      charts.forEach((chart) => chart.resize());
    });
  }

  function renderQuotes(rows, column) {
    const list = document.getElementById("quoteList");
    if (!list) return;

    const quotes = column
      ? rows.map((row) => String(row[column] ?? "").trim()).filter(Boolean).slice(0, 3)
      : [];

    list.replaceChildren();
    const content = quotes.length ? quotes : ["No se registraron opiniones abiertas en este archivo."];
    content.forEach((quote) => {
      const item = document.createElement("li");
      item.textContent = truncate(quote, 150);
      list.appendChild(item);
    });
  }

  function moveTo(slideId) {
    const root = document.querySelector("[data-presentation-root]");
    if (root?.pcPresentation) {
      root.pcPresentation.goTo(slideId, -1);
      resizeCharts();
      pendingDestination = null;
      return;
    }
    pendingDestination = slideId;
  }

  function renderPresentation(rows, headers) {
    const columns = resolveColumns(headers);
    if (!columns.edad || !columns.escuela) {
      throw new Error("No se reconocen las columnas esperadas del formulario.");
    }

    const total = rows.length;
    const ageEntries = topEntries(countSingle(rows, columns.edad), 7);
    const cycleEntries = topEntries(countSingle(rows, columns.ciclo), 7);
    const schoolEntries = topEntries(countSingle(rows, columns.escuela), 8);
    const occupationEntries = topEntries(countSingle(rows, columns.ocupacion), 5);
    const toolEntries = topEntries(countMultiple(rows, columns.herramientas), 8);
    const frequencyEntries = topEntries(countSingle(rows, columns.frecuencia), 6);
    const purposeEntries = topEntries(countMultiple(rows, columns.paraque), 7);
    const benefitEntries = topEntries(countSingle(rows, columns.beneficio), 6);
    const riskEntries = topEntries(countSingle(rows, columns.riesgo), 6);
    const ethicsEntries = topEntries(countSingle(rows, columns.etico), 6);
    const humanEntries = topEntries(countSingle(rows, columns.noReemplaza), 7);
    const averageLearning = averageNumeric(rows, columns.likertAprend);
    const averageReliability = averageNumeric(rows, columns.confiable);

    const schoolCount = Object.keys(countSingle(rows, columns.escuela)).length;
    const learningLabel = averageLearning === null ? "—" : `${averageLearning.toFixed(1)}/5`;
    const reliabilityLabel = averageReliability === null ? "—" : `${averageReliability.toFixed(1)}/5`;

    setText("kpiTotal", String(total));
    setText("kpiEscuelas", String(schoolCount));
    setText("kpiAprendizaje", learningLabel);
    setText("kpiConfiabilidad", reliabilityLabel);
    setText("metricAprendizaje", learningLabel);
    setText("metricConfiabilidad", reliabilityLabel);
    setText("titulo-panorama", `${total} respuestas sitúan el debate sobre el uso universitario de IA.`);

    const leadingAge = ageEntries[0]?.[0];
    const leadingCycle = cycleEntries[0]?.[0];
    const leadingOccupation = occupationEntries[0]?.[0];
    const profileParts = [leadingAge, leadingCycle].filter(Boolean).map((value) => truncate(value, 28));
    if (profileParts.length) {
      setText("titulo-perfil", `La muestra se concentra en ${profileParts.join(" y ")}.`);
    }

    if (toolEntries[0]) {
      setText("titulo-habitos", `${truncate(toolEntries[0][0], 38)} encabeza las herramientas declaradas.`);
    }

    if (benefitEntries[0] && riskEntries[0]) {
      setText("titulo-valor-riesgo", "El beneficio percibido debe leerse junto con el principal riesgo señalado.");
    }

    if (ethicsEntries[0]) {
      setText("titulo-criterio-etico", `La postura ética más frecuente fue “${truncate(ethicsEntries[0][0], 46)}”.`);
    }

    const insightParts = [];
    if (leadingOccupation) insightParts.push(`La ocupación más común es ${truncate(leadingOccupation, 42)}`);
    if (toolEntries[0]) insightParts.push(`${truncate(toolEntries[0][0], 42)} lidera entre las herramientas mencionadas`);
    setText(
      "panoramaInsight",
      insightParts.length ? `${insightParts.join("; ")}.` : "La muestra permite comparar perfil, hábitos, valor percibido y criterio ético."
    );

    document.body.classList.add("has-data");
    destroyCharts();

    createBarChart("chartEdad", ageEntries, false);
    createBarChart("chartCiclo", cycleEntries, false);
    createBarChart("chartEscuela", schoolEntries, true);
    createBarChart("chartHerramientas", toolEntries, true);
    createDoughnutChart("chartFrecuencia", frequencyEntries);
    createBarChart("chartParaQue", purposeEntries, true);
    createDoughnutChart("chartBeneficio", benefitEntries);
    createDoughnutChart("chartRiesgo", riskEntries);
    createDoughnutChart("chartEtico", ethicsEntries);
    createBarChart("chartNoReemplaza", humanEntries, true);
    renderQuotes(rows, columns.opinion);
    resizeCharts();
  }

  async function handleFile(file) {
    const status = document.getElementById("fileStatus");
    const error = document.getElementById("fileError");
    if (!file) return;

    error.textContent = "";
    if (!/\.xlsx$/i.test(file.name)) {
      status.textContent = "Esperando un archivo compatible…";
      error.textContent = "Selecciona un archivo .xlsx.";
      return;
    }

    if (!window.Chart) {
      error.textContent = "No se pudo cargar el componente local de gráficos.";
      return;
    }

    status.textContent = `Procesando ${file.name}…`;

    try {
      const { rows, headers } = await parseXlsx(await file.arrayBuffer());

      if (!rows.length) throw new Error("El archivo no contiene filas de datos.");

      renderPresentation(rows, headers);
      status.textContent = `✓ ${file.name} · ${rows.length} respuestas cargadas`;
      moveTo("panorama");
    } catch (caughtError) {
      console.error(caughtError);
      status.textContent = "No se cargaron datos.";
      error.textContent = caughtError instanceof Error
        ? caughtError.message
        : "No se pudo leer el archivo. Verifica que sea un Excel válido.";
    }
  }

  function initialize() {
    const root = document.querySelector("[data-presentation-root]");
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");

    if (!root || !dropZone || !fileInput) return;

    fileInput.addEventListener("change", () => handleFile(fileInput.files?.[0]));

    dropZone.addEventListener("click", (event) => {
      if (!event.target.closest("label")) fileInput.click();
    });

    dropZone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
      }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.add("is-dragging");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropZone.classList.remove("is-dragging");
      });
    });

    dropZone.addEventListener("drop", (event) => {
      handleFile(event.dataTransfer?.files?.[0]);
    });

    root.addEventListener("pc:ready", () => {
      if (pendingDestination) moveTo(pendingDestination);
    });
    root.addEventListener("pc:slideenter", resizeCharts);
    root.addEventListener("pc:resize", resizeCharts);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, { once: true });
  } else {
    initialize();
  }
})();
