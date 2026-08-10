# Templates de BibliotecaWeb

Los templates son puntos de partida copiables. No son artefactos, no se registran en `data/catalog.json` y ninguna presentación mantiene un vínculo con el template del que nació.

Los templates de presentación V1 viven a la misma profundidad que un artefacto canónico. Por ello, sus rutas `../../../../runtime/...` continúan funcionando después de copiar sus archivos a:

```text
artefactos/{areaId}/{collectionId}/{slug}/
```

Opciones iniciales:

- `presentation/v1/blank/`: estructura mínima y neutral;
- `presentation/v1/academic/`: narrativa académica con brand USMP;
- `presentation/v1/visual/`: composición gráfica sin branding.

La forma preferida de crear una presentación es:

```powershell
python tools\create_artifact.py --type presentation --area ciclo-09 --collection seguridad-auditoria --slug tema-ejemplo --title "Tema de ejemplo" --summary "Descripción pública y breve." --template academic --dry-run
```

Después de revisar la simulación, se elimina `--dry-run` para escribir y registrar el artefacto. La herramienta:

1. copia el template elegido;
2. elimina `TEMPLATE.md` de la copia;
3. cambia `presentationId`, título y metadata inicial;
4. actualiza `brandData` cuando se indica;
5. registra la ruta final en el catálogo;
6. valida todo el proyecto antes de conservar el resultado.

Al hacer una copia manual se debe:

1. cambiar `presentationId`, títulos y contenido;
2. adaptar `brandData` si corresponde;
3. diseñar libremente `presentation.css`;
4. añadir `presentation.js` solo si existe comportamiento particular;
5. registrar la carpeta final en el catálogo;
6. ejecutar `python tools\validate_project.py`.
