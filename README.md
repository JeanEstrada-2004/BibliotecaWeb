# BibliotecaWeb

BibliotecaWeb será una biblioteca personal de artefactos web estáticos publicada mediante GitHub Pages. Reunirá presentaciones, mockups y páginas independientes en un solo repositorio, sin backend, base de datos, autenticación ni build obligatorio.

## Estado actual

La implementación local de **BibliotecaWeb V1 está completa** después de ocho etapas graduales.

Actualmente están disponibles:

- la arquitectura general y el modelo de artefactos;
- el catálogo inicial;
- el portal dinámico con navegación por áreas y colecciones;
- búsqueda y filtros por tipo;
- la estructura canónica `Área → Colección → Artefacto`;
- un primer artefacto `page` independiente y publicado;
- Presentation Runtime V1 con navegación, steps, transiciones, fullscreen, eventos y Reduced Motion;
- vista general accidental desactivada y presentaciones sin enlace directo al portal;
- Reveal.js `6.0.1` fijado localmente como motor interno;
- una primera presentación académica publicada y conectada al catálogo;
- carga opcional de brands declarados por presentación;
- brand académico USMP con niveles `full`, `minimal` y `none`;
- templates `blank`, `academic` y `visual` para Presentation Runtime V1;
- creador transaccional para artefactos `presentation`, `page` y `mockup`;
- simulación `--dry-run` que trabaja sobre una copia temporal;
- validador integral de catálogo, rutas, artefactos, presentaciones, brands, templates, recursos y tamaños;
- once pruebas automatizadas para herramientas, estadísticas, accesibilidad, navegación del runtime y rollback;
- medición reproducible de la huella web publicable mediante `data/stats.json`;
- política interna configurable y separada de cualquier límite oficial externo;
- resumen discreto de crecimiento en el inicio;
- página `/estado/` con distribución por área, tipo, componente, artefacto y archivo;
- detección de archivos grandes, concentración y duplicados exactos;
- servidor local de prueba y recorrido manual documentado;
- revisión final de rutas HTTP, compatibilidad bajo subdirectorio y referencias accesibles;
- las reglas para futuros agentes;
- el contrato implementado del Presentation Runtime;
- los esquemas de validación.

La V1 queda lista para uso local y para incorporar artefactos reales. La publicación y cualquier automatización remota continúan fuera del alcance actual.

## Principios

- HTML, CSS y JavaScript estándar.
- Compatible con GitHub Pages y con rutas bajo un subdirectorio.
- Sin framework ni backend.
- Sin proceso de compilación obligatorio.
- Artefactos independientes y extraíbles.
- Recursos ligeros: CSS y SVG antes que imágenes decorativas grandes.
- Dependencias compartidas mínimas, explícitas y versionadas.
- Contenido público y libre de datos confidenciales.

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Contrato de artefactos](docs/ARTIFACTS.md)
- [Presentation Runtime](docs/PRESENTATION_RUNTIME.md)
- [Validación](docs/VALIDATION.md)
- [Medición y política de almacenamiento](docs/STORAGE.md)
- [Prueba local](docs/TESTING.md)
- [Informe de revisión V1](docs/QA_REPORT.md)
- [Templates](templates/README.md)
- [Herramientas locales](tools/README.md)
- [Instrucciones para agentes](AGENTS.md)

## Desarrollo local

La forma más sencilla de abrir el sistema es:

```powershell
python tools\serve.py
```

El navegador mostrará el portal, desde donde ya puede abrirse la presentación publicada `Introducción a la Auditoría de Sistemas`.

Validación completa:

```powershell
python tools\validate_project.py
```

Pruebas automatizadas:

```powershell
python -m unittest discover -s tools\tests -v
```

Actualizar o comprobar las estadísticas:

```powershell
python tools\build_stats.py
python tools\build_stats.py --check
```

El entorno del navegador soportado es HTTPS o un servidor HTTP local. No se garantiza el funcionamiento mediante `file://`, porque el portal utiliza módulos JavaScript y datos JSON.

## Privacidad

Todo archivo incluido en la fuente publicada debe considerarse público. Los borradores ocultos del catálogo, archivos ignorados visualmente o rutas no enlazadas no constituyen controles de acceso.
