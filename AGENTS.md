# Instrucciones para agentes

Estas reglas se aplican a todo el repositorio BibliotecaWeb.

## Antes de modificar

1. Leer `docs/ARCHITECTURE.md`.
2. Leer `docs/ARTIFACTS.md`.
3. Leer `docs/PRESENTATION_RUNTIME.md` solo si el artefacto es una presentación o si se modifica el runtime.
4. Leer `templates/README.md` si se utilizará un template.
5. Consultar `data/catalog.json` antes de elegir área, colección, identificador o slug.
6. Respetar la etapa de implementación solicitada por el usuario; no adelantar etapas sin autorización.
7. Preferir `tools/create_artifact.py` para crear y registrar un artefacto nuevo.
8. Leer `docs/STORAGE.md` si se incorporan assets o se modifica la política de tamaños.

## Arquitectura obligatoria

- Mantener HTML, CSS y JavaScript sin framework ni backend.
- No introducir un build obligatorio para ejecutar el sitio.
- Usar la ruta canónica `artefactos/{areaId}/{collectionId}/{slug}/`.
- Mantener un `index.html` como entrada de cada artefacto.
- Usar slugs ASCII en minúsculas y separados por guiones.
- Registrar cada artefacto en `data/catalog.json`.
- No codificar el nombre `BibliotecaWeb` dentro de rutas públicas.
- No utilizar rutas que comiencen con `/`; usar rutas relativas.

## Límites entre componentes

- Un artefacto no puede importar archivos de otro artefacto.
- Un mockup o una página no debe cargar el Presentation Runtime.
- Una presentación no debe importar Reveal.js directamente; debe usar el contrato del runtime.
- Una presentación V1 carga únicamente `runtime/presentation/v1/runtime.css` y `runtime/presentation/v1/bootstrap.js` mediante rutas relativas.
- El comportamiento particular escucha eventos `pc:*` o utiliza `root.pcPresentation`; nunca accede a la instancia interna de Reveal.js.
- Una presentación declara el brand mediante `brand` y datos públicos mediante `brandData`; no importa archivos de `brands/` directamente.
- Un template se copia y luego se desvincula: no se importa ni se registra en el catálogo.
- No modificar `runtime/`, `brands/`, `vendor/` ni artefactos existentes para resolver una necesidad exclusiva de un artefacto nuevo.
- No reutilizar CSS o JavaScript del portal dentro de un artefacto.
- Las dependencias compartidas nuevas requieren una necesidad repetida y una decisión arquitectónica explícita.

## Assets

- Priorizar HTML, CSS y SVG para decoración, diagramas e iconografía.
- Utilizar raster solo cuando aporte contenido o evidencia visual real.
- Optimizar dimensiones y peso de imágenes antes de incorporarlas.
- Mantener los assets propios dentro de la carpeta del artefacto.
- No enlazar assets desde otro artefacto ni usar hotlinks externos sin autorización.
- No insertar binarios grandes como Base64.
- No editar `data/stats.json` manualmente; regenerarlo con `python tools/build_stats.py`.
- Tratar `data/storage-policy.json` como política interna, nunca como un límite oficial externo.

## Seguridad y privacidad

- No incluir secretos, credenciales, datos personales sensibles ni información laboral confidencial.
- Considerar público todo archivo dentro de la fuente publicada.
- `draft` oculta un artefacto del portal, pero no protege su URL.
- Si un mockup usa almacenamiento local, las claves deben comenzar con `biblioteca:{artifact-id}:`.
- No añadir service workers sin una revisión explícita de su alcance.

## Finalización

- Ejecutar `python tools/validate_project.py` para validar JSON, referencias, rutas, casing y archivos requeridos.
- Ejecutar `python tools/build_stats.py --check` para confirmar que la huella calculada está vigente.
- Ejecutar `python -m unittest discover -s tools/tests -v` si se modificaron herramientas o contratos de validación.
- Comprobar que no existan enlaces o recursos rotos.
- Informar el peso añadido cuando las herramientas de estadísticas estén disponibles.
- No hacer commit, push, despliegue ni publicación salvo solicitud explícita del usuario.
