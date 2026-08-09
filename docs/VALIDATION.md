# Estrategia de validación

## Estado

La validación local determinista está implementada con Python estándar y sin dependencias externas:

```powershell
python tools\validate_project.py
```

El comando devuelve código `0` cuando no hay errores y código `1` cuando encuentra al menos uno. `--strict` también convierte los avisos en fallo, `--json` produce una salida procesable y `--quiet` muestra solo el resumen.

Cada hallazgo incluye severidad, código estable, archivo o campo exacto y explicación. La herramienta no corrige contenido automáticamente.

## Catálogo

El validador comprueba:

- sintaxis JSON y versión de contrato soportada;
- forma y campos permitidos de áreas, colecciones, tipos y artefactos;
- IDs, slugs y órdenes;
- referencias cruzadas;
- unicidad global de IDs y local de colecciones y slugs;
- ruta canónica derivada y casing exacto;
- estado, fechas ISO, tags y metadata opcional;
- `publishedAt` obligatorio para artefactos publicados;
- cover existente, relativo y contenido dentro del artefacto;
- carpetas registradas ausentes y carpetas no registradas.

Los archivos de `schemas/` documentan la forma pública. Las comprobaciones cruzadas y del sistema de archivos viven en `tools/project_validation.py` para que el creador reutilice exactamente el mismo contrato.

## Artefactos y fuentes

Para todos los artefactos se comprueba:

- presencia de `index.html`, exactamente un `main` y un `h1`;
- idioma `es`, título, viewport y jerarquía de encabezados sin saltos;
- IDs HTML no repetidos, referencias ARIA/labels resolubles e imágenes con `alt`;
- botones HTML con `type` explícito;
- recursos y enlaces locales resolubles;
- ausencia de rutas públicas absolutas o que salgan del proyecto;
- ausencia de imports entre artefactos o hacia el portal;
- límites de dependencia según `presentation`, `page` y `mockup`;
- ausencia de `innerHTML`, `eval()`, `new Function()` y claves privadas embebidas;
- archivos con nombres sensibles, Base64 grande y tamaños anómalos;
- assets propios sin referencia.

El portal, los recursos compartidos, el runtime, los brands y los templates pasan por las mismas comprobaciones de fuentes aplicables.

## Estadísticas

El validador exige:

- `data/storage-policy.json` válido y reconocible como política interna;
- `data/stats.json` con versión, alcance y fecha compatibles;
- correspondencia exacta entre su fingerprint, desgloses y los archivos actuales;
- schemas documentales presentes para política y estadísticas.

Si cualquier archivo publicable, artefacto, catálogo o política cambia, aparece `stats-stale` hasta ejecutar:

```powershell
python tools\build_stats.py
```

## Presentaciones, brands y templates

Presentaciones:

- `presentation.config.json` y `presentation.css` obligatorios;
- contrato y `presentationId` coherentes con el catálogo;
- slides e IDs únicos, steps válidos y chrome soportado;
- configuración de transiciones y features;
- carga mediante puntos públicos del runtime, nunca del motor o brand internos.

Brands:

- carpeta con slug válido, `brand.css`, `brand.js` y `VERSION`;
- módulo con `mountBrand`, `update` y `destroy`;
- independencia frente al runtime y al motor interno.

Templates:

- archivos base y configuración válidos;
- IDs de ejemplo con prefijo `template-`;
- markup de presentación válido;
- ausencia de dependencias hacia otros templates.

Mockups que usen `localStorage` deben incluir el namespace `biblioteca:{artifact-id}:`.

## Pruebas automatizadas

```powershell
python -m unittest discover -s tools\tests -v
```

La suite comprueba el proyecto actual, la ubicación exacta de errores de catálogo y ARIA, `dry-run` sin escrituras, creación de páginas y presentaciones, rechazo de duplicados, rollback de carpeta/catálogo/estadísticas, reproducción exacta de `stats.json` y detección de estadísticas obsoletas.

## Alcance pendiente

Todavía se comprobarán manualmente en un servidor HTTP:

- funcionamiento e interacción reales en navegador;
- responsive, teclado, foco y Reduced Motion;
- errores de consola y red;
- navegación directa, hashes y fullscreen.

Los presupuestos históricos, tendencias entre versiones y comparación con referencias externas pertenecen a una etapa posterior.
