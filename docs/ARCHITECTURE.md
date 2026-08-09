# Arquitectura de BibliotecaWeb

## Propósito

BibliotecaWeb organiza y publica artefactos web estáticos personales, académicos y profesionales desde un único sitio de GitHub Pages.

El sistema debe permanecer sencillo de mantener por una persona y predecible para agentes de IA. No pretende ser un CMS, un editor visual, un monorepo de aplicaciones productivas ni un servicio con backend.

## Capas

```text
Portal ───────────────► Catálogo
                            │
                            ▼
                      Artefactos

Presentación ─────────► Presentation Runtime versionado
                            │
                            ├── Motor interno fijado
                            └── Brand opcional

Herramientas ─────────► Catálogo, validación y estadísticas
```

### Portal

Es la entrada de la biblioteca. Presenta áreas, colecciones, búsqueda, filtros y enlaces. Solo depende del catálogo y de sus propios recursos.

El portal no carga el Presentation Runtime ni conoce la estructura interna de un artefacto.

### Catálogo

`data/catalog.json` es la fuente central de metadatos públicos. Contiene áreas, colecciones, tipos y artefactos.

El catálogo describe cómo localizar, clasificar y mostrar un artefacto. No almacena decisiones internas de diseño, animación o comportamiento.

### Artefactos

Cada artefacto es un documento o aplicación web estática con un `index.html` propio. Los tipos iniciales son:

- `presentation`;
- `mockup`;
- `page`.

Los tipos representan contratos técnicos. No se crea un tipo nuevo únicamente para añadir una etiqueta temática.

### Presentation Runtime

Es una dependencia opcional y exclusiva de las presentaciones. Proporciona navegación, slides, steps, transiciones, progreso, fullscreen, Reduced Motion, eventos y carga opcional de brands.

El runtime tendrá versiones mayores estables (`runtime/presentation/v1/`, `v2/`, etc.). Una presentación antigua no debe romperse por la creación de una versión nueva.

### Brands

Los brands proporcionan identidad institucional reutilizable sin controlar el diseño del contenido. Su carga es opcional y explícita.

Los mockups y páginas no reciben branding global automáticamente.

Cada brand posee CSS y JavaScript propios bajo `brands/{brandId}/`. El runtime le entrega únicamente datos públicos normalizados, el slide activo y el nivel de chrome; nunca le entrega la instancia del motor interno.

### Templates

Los templates son copias iniciales, no dependencias. Viven bajo `templates/presentation/v1/` a la misma profundidad que un artefacto canónico para conservar las rutas relativas al copiarlos.

Una presentación creada desde un template no mantiene referencia hacia él. Los templates tampoco se registran en el catálogo.

### Herramientas

Las herramientas locales mantienen responsabilidades separadas:

- `tools/create_artifact.py` crea y registra artefactos de forma transaccional;
- `tools/validate_project.py` valida estructura, semántica, dependencias, recursos y límites básicos;
- `tools/build_stats.py` calcula y verifica la huella web publicable;
- `tools/project_validation.py` contiene el contrato reutilizable por ambos comandos;
- `tools/project_stats.py` mantiene el cálculo y la política de agrupación;
- `tools/tests/` comprueba creación, simulación, errores precisos y rollback.

La revisión estructural y HTTP de V1 está automatizada. La comprobación visual e interactiva permanece como un recorrido manual breve descrito en `docs/TESTING.md`, sin incorporar un navegador pesado al proyecto.

No forman parte del código ejecutado por el navegador.

## Organización de carpetas objetivo

```text
BibliotecaWeb/
├── index.html
├── app/
├── data/
├── estado/
├── artefactos/
│   ├── ciclo-09/
│   ├── ciclo-10/
│   ├── trabajo/
│   └── personal/
├── runtime/
│   └── presentation/
│       └── v1/
├── brands/
├── vendor/
├── shared/
├── templates/
├── schemas/
├── tools/
└── docs/
```

Las carpetas se crearán cuando su etapa de implementación las necesite. No se conservarán árboles vacíos únicamente para representar la arquitectura.

## Rutas canónicas

Todos los artefactos usan la misma profundidad:

```text
artefactos/{areaId}/{collectionId}/{slug}/
```

Ejemplos:

```text
artefactos/ciclo-09/inteligencia-negocios/data-warehouses/
artefactos/trabajo/general/mockup-rendicion-gastos/
artefactos/personal/general/pagina-para-amigo/
```

El tipo no forma parte de la ruta. Esto permite cambiar la clasificación técnica sin alterar la URL y facilita extraer un área completa.

## Reglas de dependencia

Dependencias permitidas:

```text
Portal -> Catálogo
Presentación -> Presentation Runtime vN
Presentación -> Brand declarado
Runtime -> Motor interno fijado
```

Dependencias prohibidas:

```text
Portal -> Presentation Runtime
Artefacto A -> Artefacto B
Mockup -> Presentation Runtime
Página -> Presentation Runtime
Artefacto -> CSS o JS del portal
Artefacto -> Código interno no versionado
```

## Separabilidad

Un artefacto debe poder extraerse copiando su carpeta y, cuando corresponda, las dependencias versionadas que declare su tipo.

Para conservar esta propiedad:

- los assets particulares viven junto al artefacto;
- no existen imports entre artefactos;
- las rutas son relativas;
- el nombre del repositorio no se codifica en HTML, CSS o JavaScript;
- las dependencias compartidas son pocas y versionadas;
- el catálogo deriva las rutas de IDs y slug.

## GitHub Pages

BibliotecaWeb debe funcionar como project site bajo un subdirectorio. Por ello, las rutas públicas no comienzan con `/` y no incluyen manualmente el nombre del repositorio.

El entorno compatible es HTTPS o un servidor HTTP local. `file://` no forma parte del contrato.

Todo contenido publicado se considera público. Un estado `draft`, la ausencia de un enlace o una regla de `.gitignore` no sustituyen un control de acceso.

## Implementación actual

El portal está implementado como una página estática que carga `data/catalog.json`, usa navegación por hash y deriva todas las rutas de artefactos a partir de sus metadatos. Sus estilos y comportamiento viven exclusivamente en `app/`.

La ruta canónica ya está comprobada mediante un primer artefacto independiente de tipo `page` en `artefactos/personal/general/anatomia-biblioteca-web/`. Este artefacto utiliza exclusivamente archivos locales y no depende del portal ni del Presentation Runtime.

Presentation Runtime V1 está implementado en `runtime/presentation/v1/` y adapta Reveal.js `6.0.1`, fijado localmente, al contrato público de BibliotecaWeb. La primera presentación canónica vive en `artefactos/ciclo-09/seguridad-auditoria/introduccion-auditoria-sistemas/` y solo importa los puntos de entrada versionados del runtime.

El runtime V1.1 carga el brand académico `usmp` cuando una presentación lo declara. Los templates `blank`, `academic` y `visual` sirven como tres puntos de partida independientes sin imponer una estética común.

Las herramientas locales ya permiten validar el proyecto completo y crear artefactos `presentation`, `page` y `mockup`. El creador simula en una copia temporal con `--dry-run`; al escribir, actualiza carpeta y catálogo como una operación con rollback y conserva el resultado únicamente si la validación final termina sin errores.

La huella publicable se calcula previamente en `data/stats.json`; el portal consume un resumen y `/estado/` presenta el detalle. `data/storage-policy.json` contiene únicamente criterios internos de mantenimiento. El generador separa artefactos de infraestructura y excluye el propio archivo generado para evitar una medición autorreferente.

## Decisiones diferidas

Todavía no están implementados ni cerrados:

- GitHub Actions;
- automatización visual en navegador, si llega a justificar su dependencia;
- camera y escenas complejas.

Estas decisiones deben respetar los contratos establecidos aquí.
