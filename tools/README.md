# Herramientas locales

Los scripts requieren Python 3.10 o posterior, usan únicamente la biblioteca estándar y no ejecutan operaciones de Git, publicación o despliegue.

## Abrir la biblioteca localmente

```powershell
python tools\serve.py
```

Valida el proyecto, sirve los archivos solo en `127.0.0.1`, abre el navegador predeterminado y muestra también la URL directa de la presentación de prueba. `--no-open` evita abrir el navegador y `--port NUMERO` cambia el puerto.

## Actualizar estadísticas

```powershell
python tools\build_stats.py
```

El comando mide la huella web publicable, actualiza `data/stats.json` y termina validando el proyecto. Para comprobar que el archivo sigue vigente sin escribir:

```powershell
python tools\build_stats.py --check
```

`--json` muestra el cálculo completo y `--root RUTA` trabaja sobre otra copia. La política vive en `data/storage-policy.json`; `data/stats.json` es generado y no debe editarse manualmente.

## Validar BibliotecaWeb

```powershell
python tools\validate_project.py
```

Opciones:

- `--strict`: los avisos también producen código de salida `1`;
- `--json`: entrega el reporte completo como JSON;
- `--quiet`: muestra únicamente el resumen;
- `--root RUTA`: valida otra copia del proyecto.

Ejemplo procesable:

```powershell
python tools\validate_project.py --strict --json
```

## Crear un artefacto

Primero conviene ejecutar una simulación:

```powershell
python tools\create_artifact.py --type presentation --area ciclo-09 --collection seguridad-auditoria --slug controles-de-acceso --title "Controles de acceso" --summary "Presentación sobre principios y revisión de controles de acceso." --template academic --tag seguridad --dry-run
```

Si el resultado es correcto, se repite el comando sin `--dry-run`. El creador valida el estado inicial, genera una carpeta temporal, prepara el catálogo, aplica ambos cambios y vuelve a validar. Si la validación final falla, restaura el catálogo y elimina únicamente la carpeta recién creada.

La creación real también regenera `data/stats.json`. Si algo falla, el rollback restaura conjuntamente carpeta, catálogo y estadísticas.

Tipos admitidos:

- `presentation`: copia `blank`, `academic` o `visual` desde `templates/presentation/v1/`;
- `page`: genera `index.html`, `styles.css` y `script.js` independientes;
- `mockup`: genera la misma base independiente, preparada para desarrollar un flujo.

Ejemplo de página:

```powershell
python tools\create_artifact.py --type page --area personal --collection general --slug mapa-de-ideas --title "Mapa de ideas" --summary "Página interactiva para organizar ideas relacionadas." --tag organización
```

Ejemplo de mockup todavía en borrador:

```powershell
python tools\create_artifact.py --type mockup --area trabajo --collection general --slug flujo-de-solicitudes --title "Flujo de solicitudes" --summary "Prototipo demostrativo del recorrido de una solicitud."
```

Opciones relevantes:

- `--id`: ID estable; si se omite se deriva de área, colección y slug;
- `--status`: `draft`, `published` o `archived`; por defecto `draft`;
- `--published-at`: fecha `YYYY-MM-DD`; para `published` se usa hoy si se omite;
- `--tag`: se puede repetir;
- `--featured`: marca el artefacto como destacado;
- `--template`: `blank`, `academic` o `visual` para presentaciones;
- `--brand`: reemplaza el brand del template; `none` lo desactiva;
- `--brand-data CLAVE=VALOR`: se puede repetir para datos públicos del brand;
- `--root RUTA`: trabaja sobre otra copia de BibliotecaWeb.

El título, resumen y contenido generado son públicos. No se deben pasar secretos ni datos personales sensibles como argumentos.

## Ejecutar pruebas

```powershell
python -m unittest discover -s tools\tests -v
```

Las pruebas crean copias temporales; no registran artefactos en la biblioteca real.
