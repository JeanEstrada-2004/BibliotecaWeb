# Contrato de artefactos

## Definición

Un artefacto es una unidad web estática publicable, identificable y extraíble. Todos los artefactos tienen una entrada `index.html`, una ruta canónica y un registro en el catálogo.

## Tipos iniciales

### `presentation`

Presentación web basada en slides. Es el único tipo que utiliza el Presentation Runtime.

Estructura requerida:

```text
index.html
presentation.config.json
presentation.css
presentation.js        opcional
assets/                opcional
```

### `mockup`

Aplicación web estática que simula una interfaz o flujo. Puede tener múltiples vistas, navegación, formularios, tablas, modales y estado local de demostración.

No usa el Presentation Runtime. Su estructura interna es libre, pero debe permanecer dentro de su carpeta.

### `page`

Página, demo o experimento web independiente que no necesita el contrato de presentación ni la complejidad semántica de un mockup.

No usa el Presentation Runtime.

## Área y colección

La ubicación se determina mediante:

```text
Área -> Colección -> Artefacto
```

- En `ciclo-09` y `ciclo-10`, una colección representa normalmente un curso.
- En `trabajo`, una colección representa una agrupación mantenible como `general`, `capacitaciones` o `propuestas`.
- En `personal`, se usa `general` hasta que exista una necesidad real de otra colección.

No se crean carpetas por tipo. El tipo es metadata.

## Identificadores

`id`, `areaId`, `collectionId`, `type` y `slug` utilizan ASCII en minúsculas con guiones.

Patrón:

```text
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

El `id` de un artefacto es estable y único en toda la biblioteca. Un `collectionId` es único dentro de su área y se resuelve mediante el par `(areaId, collectionId)`. El `slug` es único dentro de una colección.

## Ruta

La ruta no se guarda manualmente. Se deriva como:

```text
artefactos/{areaId}/{collectionId}/{slug}/
```

Cada segmento debe coincidir exactamente en casing con el catálogo.

## Creación local

La vía preferida es `tools/create_artifact.py`, que comprueba IDs y referencias, genera la carpeta canónica, registra el catálogo, actualiza las estadísticas y revierte los tres cambios si la validación final falla. `--dry-run` ejecuta el mismo flujo sobre una copia temporal.

Los comandos y opciones se documentan en `tools/README.md`. Una creación manual sigue siendo válida si respeta este contrato y termina con `python tools/validate_project.py`.

## Catálogo

El archivo `data/catalog.json` contiene:

- `schemaVersion`;
- `areas`;
- `collections`;
- `types`;
- `artifacts`.

Campos comunes de un artefacto:

- `id`;
- `title`;
- `slug`;
- `areaId`;
- `collectionId`;
- `type`;
- `summary`;
- `status`;
- `publishedAt` cuando está publicado;
- `updatedAt` cuando resulte necesario;
- `tags`;
- `cover` opcional, relativo a la carpeta del artefacto;
- `featured` opcional.

`details` se reserva para metadata pública y específica de un tipo que el portal necesite mostrar. No debe contener configuración visual ni lógica del artefacto.

## Estados

- `draft`: no se muestra normalmente en el portal.
- `published`: visible y compartible.
- `archived`: conservado, pero fuera del flujo principal.

Ningún estado proporciona privacidad. Si la carpeta está publicada, su contenido puede ser accesible.

## Assets

Cada artefacto es propietario de sus assets particulares.

Política:

- HTML, CSS y SVG como primera opción para decoración e interfaces;
- imágenes rasterizadas solo cuando aportan información o evidencia;
- dimensiones y compresión adecuadas al uso real;
- nada de hotlinks externos sin autorización;
- nada de recursos importados desde otro artefacto;
- nada de binarios grandes codificados como Base64;
- texto alternativo para imágenes informativas;
- procedencia y licencia documentadas cuando corresponda.

Un asset pequeño puede duplicarse si ello mejora la independencia. Solo se comparte un recurso cuando es estable, se reutiliza de forma real y su centralización aporta más que el acoplamiento creado.

## Estado local

Los mockups pueden usar almacenamiento local únicamente para demostración. Las claves deben usar:

```text
biblioteca:{artifact-id}:{key}
```

No se permite tratar `localStorage` como autenticación, almacenamiento seguro o base de datos productiva.

## Extracción futura

Para mover un artefacto a otro repositorio:

1. copiar su carpeta;
2. copiar las dependencias versionadas declaradas por su tipo;
3. exportar o adaptar su entrada del catálogo;
4. ajustar el punto de publicación sin reescribir su contenido.

No se diseñará todavía una herramienta de extracción; el contrato debe hacerla posible.

## Caso de referencia actual

`artefactos/personal/general/anatomia-biblioteca-web/` es el primer artefacto publicado y sirve como referencia del contrato genérico:

- está registrado como `page`;
- posee `index.html`, CSS y JavaScript propios;
- no carga el portal ni el Presentation Runtime;
- no utiliza dependencias, fuentes o recursos externos;
- puede abrirse directamente mediante su URL canónica;
- utiliza únicamente un enlace relativo para regresar a la biblioteca.

Este caso demuestra independencia técnica. No debe convertirse en una plantilla visual obligatoria para artefactos futuros.

`artefactos/ciclo-09/seguridad-auditoria/introduccion-auditoria-sistemas/` es el primer caso canónico de tipo `presentation`:

- está registrado y publicado en el catálogo;
- carga exclusivamente `runtime/presentation/v1/runtime.css` y `bootstrap.js`;
- mantiene contenido, estilos y comportamiento particular dentro de su carpeta;
- utiliza steps declarativos y eventos `pc:*` sin acceder al motor interno;
- declara el brand `usmp` y sus datos públicos en la configuración local;
- puede compartirse mediante su ruta directa y hashes de slide;
- no funciona como template visual obligatorio.

Los templates de `templates/presentation/v1/` no son artefactos: no se registran en el catálogo, no poseen estado de publicación y solo sirven como fuentes para copiar. Al crear el artefacto final se cambia su ID, contenido y configuración.
