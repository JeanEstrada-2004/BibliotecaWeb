# Medición y política de almacenamiento

## Propósito

BibliotecaWeb mide su crecimiento antes de que el tamaño dificulte mantener, revisar o separar los artefactos. Esta medición sirve para tomar decisiones internas; no representa un límite oficial de un proveedor de alojamiento.

## Archivos

- `data/storage-policy.json`: configuración humana y versionada de la política interna.
- `data/stats.json`: resultado generado que consumen el portal y `/estado/`.
- `tools/project_stats.py`: cálculo reutilizable.
- `tools/build_stats.py`: comando de actualización y comprobación.

`data/stats.json` no se edita manualmente.

## Alcance medido

Se incluye la huella web publicable:

- archivos públicos de la raíz;
- `app/`;
- `artefactos/`;
- `brands/`;
- `data/`;
- `estado/`;
- `runtime/`;
- `shared/`;
- `vendor/`.

Se excluyen documentación, schemas, templates, herramientas, pruebas y cachés. También se excluye el propio `data/stats.json` para evitar que el cálculo cambie por contener su propio resultado.

La medida representa archivos actuales, no historial de control de versiones, transferencia, memoria ni tiempo de carga.

## Política interna inicial

El presupuesto inicial es **200 MiB**. Es un margen deliberadamente conservador para mantener una biblioteca estática ligera y separable; puede revisarse cuando existan más artefactos reales.

Niveles actuales:

- `Excelente`: desde 0% del presupuesto;
- `Normal`: desde 20%;
- `Vigilar`: desde 45%;
- `Considerar separación`: desde 70%;
- `Crítico`: desde 90%.

La política también advierte inicialmente sobre:

- archivos mayores de 5 MiB;
- artefactos mayores de 25 MiB;
- archivos duplicados exactos de al menos 4 KiB;
- concentración de 65% o más por área o tipo, cuando existan al menos cinco artefactos.

Todos estos valores son configurables en bytes o porcentajes. Cambiar la política requiere regenerar las estadísticas.

## Datos calculados

El generador produce:

- total, peso de artefactos e infraestructura compartida;
- número de archivos y artefactos;
- peso por área, tipo y componente;
- peso y cantidad de archivos de cada artefacto;
- archivos más pesados;
- duplicados exactos mediante SHA-256;
- alertas de tamaño o concentración;
- fingerprint de todos los archivos medidos.

La fecha se guarda como ISO 8601 con zona horaria. Los tamaños permanecen como enteros en bytes y las interfaces los formatean para lectura humana.

## Flujo local

Actualizar:

```powershell
python tools\build_stats.py
```

Comprobar sin escribir:

```powershell
python tools\build_stats.py --check
```

Crear un artefacto mediante `tools/create_artifact.py` actualiza las estadísticas automáticamente dentro de la misma operación transaccional.
