# Presentation Runtime V1

## Estado

El runtime está implementado en `runtime/presentation/v1/`. Su contrato público es V1 y su versión de implementación actual es `1.2.0`.

Reveal.js `6.0.1` funciona como motor interno fijado localmente en `vendor/reveal/6.0.1/`. Las presentaciones no importan, configuran ni utilizan directamente su API.

El branding opcional está implementado mediante módulos locales bajo `brands/{brandId}/`. El brand académico inicial es `usmp`.

## Propósito

El Presentation Runtime comparte capacidades, no apariencia. Cada presentación conserva control sobre su composición, paleta, tipografía, contenido y comportamiento particular.

Capacidades implementadas:

- slides planas en relación 16:9;
- navegación mediante controles, teclado y touch;
- progreso y número de slide;
- pantalla completa mediante botón o tecla `F`;
- regreso a BibliotecaWeb mediante un control común;
- steps declarativos y reversibles;
- transiciones `none`, `fade`, `slide` y `zoom`;
- efectos de step `fade`, `fade-up`, `scale-in`, `appear` y `none`;
- URLs compartibles por hash;
- Reduced Motion en CSS y JavaScript;
- eventos DOM estables;
- API limitada por instancia;
- carga opcional y aislada de brands;
- JavaScript particular opcional;
- mensajes legibles cuando la configuración o el DOM son inválidos.
- vista general de miniaturas desactivada para evitar cambios de escala accidentales al usar `Esc`.

## Archivos de una presentación

```text
index.html
presentation.config.json
presentation.css
presentation.js        opcional
assets/                opcional
```

La presentación carga únicamente los puntos públicos del runtime:

```html
<link
  rel="stylesheet"
  href="../../../../runtime/presentation/v1/runtime.css"
>

<script
  type="module"
  src="../../../../runtime/presentation/v1/bootstrap.js"
></script>
```

La cantidad de segmentos `../` deriva de la ruta canónica del artefacto. No se debe escribir el nombre del repositorio ni usar rutas que comiencen con `/`.

## Raíz y slides

La raíz declara el archivo de configuración y contiene `.slides` como hijo directo:

```html
<main
  class="reveal"
  data-presentation-root
  data-presentation-config="presentation.config.json"
>
  <div class="slides">
    <section
      data-slide
      data-slide-id="gestion-riesgos"
      data-transition="fade"
      data-brand-chrome="minimal"
    >
      <!-- contenido libre -->
    </section>
  </div>
</main>
```

Reglas V1:

- cada hijo directo de `.slides` es un `section[data-slide]`;
- cada slide tiene un `data-slide-id` único con formato slug;
- el `id` HTML, si se declara, coincide con `data-slide-id`;
- no existen slides verticales o anidadas;
- `data-transition` es opcional y reemplaza la transición predeterminada;
- `data-brand-chrome` acepta `full`, `minimal` o `none`.

## Steps

Un step es un estado incremental dentro de una slide. La navegación recorre todos los steps antes de avanzar a la siguiente slide y los revierte al retroceder.

```html
<p
  data-step
  data-step-id="definicion"
  data-step-effect="fade-up"
>
  Un riesgo combina probabilidad e impacto.
</p>
```

`data-step-index` es opcional y debe ser un entero no negativo. Varios elementos con el mismo índice aparecen o desaparecen juntos:

```html
<span data-step data-step-id="amenaza" data-step-index="0">Amenaza</span>
<span data-step data-step-id="operador" data-step-index="0">×</span>
```

Cada `data-step-id` es único dentro de su slide. El código particular debe derivar su escena de los steps actualmente visibles y evitar mutaciones acumulativas.

## Configuración

`presentation.config.json` contiene datos y se valida antes de inicializar el motor:

```json
{
  "contractVersion": 1,
  "presentationId": "sasi-introduccion-auditoria",
  "brand": "usmp",
  "brandData": {
    "faculty": "Facultad de Ingeniería y Arquitectura",
    "school": "Escuela Profesional de Ingeniería de Computación y Sistemas",
    "course": "Seguridad y Auditoría de Sistemas de Información"
  },
  "homeHref": "../../../../",
  "aspectRatio": "16:9",
  "chromeDefault": "none",
  "transition": {
    "default": "slide",
    "durationMs": 600
  },
  "features": {
    "controls": true,
    "progress": true,
    "slideNumber": true,
    "keyboard": true,
    "touch": true,
    "fullscreen": true
  }
}
```

El esquema normativo está en `schemas/presentation-config.schema.json`. No se permiten campos adicionales.

`brandData` es opcional, requiere un `brand` declarado y solo admite claves camelCase con valores de texto o `null`. Cada texto puede contener hasta 160 caracteres. Debe incluir únicamente información pública adecuada para el sitio.

`homeHref` es opcional y por defecto utiliza `../../../../`, que corresponde a la profundidad canónica. Solo acepta una ruta local relativa y puede adaptarse si la presentación se extrae a otra ubicación.

## Branding

El runtime resuelve un brand declarado mediante:

```text
brands/{brandId}/brand.css
brands/{brandId}/brand.js
```

El módulo exporta `mountBrand()` y devuelve un controlador con `update()` y `destroy()`. El runtime le entrega:

- la raíz de la presentación;
- `brandData` normalizado;
- el slide y estado actuales;
- el nivel `full`, `minimal` o `none`.

El brand no recibe Reveal.js, no navega y no modifica el contenido de las slides. Su overlay utiliza `pointer-events: none` para permanecer separado de la interacción.

`brands/usmp/` implementa una identidad académica tipográfica con denominación institucional, facultad, escuela, curso y autor opcional. No copia ni sustituye el logotipo oficial.

## Teclado y navegación

Cuando las funciones correspondientes están activas:

- `←` y `→`: retroceder o avanzar;
- `Space`: avanzar;
- `Home`: ir al comienzo;
- `End`: ir al final;
- `F`: entrar o salir de pantalla completa;
- `Esc`: salir de pantalla completa.

Los controles, el progreso, el número de slide y el enlace `← Biblioteca` pertenecen al runtime. La vista general de Reveal.js permanece desactivada. Una presentación puede adaptar el color de los controles mediante variables CSS, pero no debe depender de las clases internas del motor.

## Eventos públicos

Los eventos se disparan sobre `[data-presentation-root]`:

- `pc:ready`;
- `pc:slideleave`;
- `pc:slideenter`;
- `pc:stepchange`;
- `pc:resize`;
- `pc:destroy`.

Los eventos de navegación incluyen:

```javascript
{
  previous: { /* estado anterior */ },
  current: { /* estado actual */ },
  direction: "next" | "previous" | "none"
}
```

El estado público contiene `presentationId`, `slideId`, `slideIndex`, `slideCount`, `stepIndex`, `stepCount` y `activeStepIds`. `stepIndex` vale `-1` cuando todavía no hay un step visible.

Ejemplo de comportamiento particular:

```javascript
const root = document.querySelector("[data-presentation-root]");

root.addEventListener("pc:stepchange", (event) => {
  const { slideId, activeStepIds } = event.detail.current;
  // Derivar la escena de este estado, sin acceder al motor interno.
});
```

## API limitada

Después de `pc:ready`, la raíz expone `root.pcPresentation`:

```javascript
root.pcPresentation.next();
root.pcPresentation.previous();
root.pcPresentation.goTo("arquitectura", 2);
root.pcPresentation.getState();
root.pcPresentation.toggleFullscreen();
root.pcPresentation.destroy();
```

No se crean funciones globales y la instancia de Reveal.js no se expone mediante este contrato.

## Estilos y aislamiento

`runtime.css` carga el CSS del motor, las transiciones y Reduced Motion. `presentation.css` se carga después y controla la identidad del contenido.

Variables públicas iniciales:

```css
:root {
  --pc-viewport-background: #07110f;
  --pc-slide-background: #07110f;
  --pc-runtime-accent: #a7f3d0;
  --pc-runtime-ink: #f4fff9;
  --pc-runtime-control: rgb(4 18 15 / 78%);
}
```

Una presentación no debe sobrescribir controles mediante selectores internos ni importar hojas de estilo de otra presentación.

## Reduced Motion

El runtime consulta `prefers-reduced-motion`, cambia las transiciones de slide a `none` y reduce animaciones, filtros y desplazamientos a un cambio prácticamente instantáneo. También reacciona si la preferencia cambia durante la sesión.

## Caso canónico

`artefactos/ciclo-09/seguridad-auditoria/introduccion-auditoria-sistemas/` demuestra:

- configuración válida;
- seis slides planas;
- navegación y fullscreen;
- regreso a la biblioteca;
- las cuatro transiciones disponibles;
- steps automáticos y steps simultáneos;
- código particular mediante eventos;
- reversibilidad al avanzar y retroceder;
- diseño independiente construido con HTML y CSS.
- brand USMP alternado por slide mediante `full`, `minimal` y `none`.

No constituye una plantilla visual obligatoria.

## Fuera de V1

Permanecen fuera del núcleo:

- slides verticales;
- camera, pan y zoom avanzado;
- escenas continuas genéricas;
- componentes temáticos compartidos;
- plugins públicos;
- editor visual;
- inicialización directa de Reveal.js.

Camera podrá añadirse posteriormente gracias a los steps identificables, los eventos, el DOM persistente y la API versionada. No se crearán APIs vacías antes de contar con casos reales.

## Prohibiciones

Una presentación no debe:

- importar Reveal.js directamente;
- modificar archivos de `runtime/` o `vendor/`;
- usar clases o API internas del motor;
- importar CSS o JavaScript de otra presentación;
- depender del nombre del repositorio;
- registrar listeners globales sin limpieza;
- ignorar Reduced Motion;
- inicializar o reemplazar el runtime desde `presentation.js`.
