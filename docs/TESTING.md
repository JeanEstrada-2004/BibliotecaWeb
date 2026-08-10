# Prueba local de BibliotecaWeb

## Inicio rápido

Desde la carpeta raíz:

```powershell
python tools\serve.py
```

El comando valida el proyecto, inicia un servidor únicamente en el equipo local y abre la biblioteca en el navegador predeterminado. Se detiene con `Ctrl+C`.

Si el navegador no debe abrirse automáticamente:

```powershell
python tools\serve.py --no-open
```

## Contenido disponible para probar

Aunque la biblioteca todavía tiene poco contenido, ya existe una presentación publicada y completa:

```text
9.º ciclo
└── Seguridad y Auditoría de Sistemas de Información
    └── Introducción a la Auditoría de Sistemas
```

También existe la página interactiva `Anatomía de BibliotecaWeb` dentro de `Personal / Extras`.

## Recorrido recomendado

### Portal

1. Confirmar que aparecen cuatro áreas.
2. Buscar `auditoría`.
3. Filtrar por `Presentación` y luego por `Página`.
4. Entrar en `9.º ciclo` y abrir `Seguridad y Auditoría de Sistemas de Información`.
5. Copiar el enlace de un artefacto.
6. Abrir `Ver estado completo` y regresar al portal.

### Presentación de prueba

Abrir `Introducción a la Auditoría de Sistemas` y comprobar:

- flechas izquierda y derecha;
- `Espacio` para avanzar;
- `Home` y `End` para ir al inicio y al final;
- pasos internos que aparecen antes de cambiar de diapositiva;
- contador y progreso;
- botón o tecla `F` para pantalla completa y `Esc` para salir;
- ausencia de enlaces directos hacia el portal dentro de la presentación;
- ausencia de la cuadrícula de miniaturas al presionar `Esc` fuera de fullscreen;
- recarga conservando el hash de la diapositiva;
- lectura y controles en una ventana estrecha o móvil.

### Estado

Comprobar:

- tamaño total y nivel interno;
- distribución por área, tipo y componente;
- artefactos y archivos más pesados;
- alertas de mantenimiento;
- adaptación a una ventana estrecha.

## Antes de considerar una modificación terminada

```powershell
python tools\build_stats.py --check
python tools\validate_project.py --strict
python -m unittest discover -s tools\tests -v
```

No se debe abrir el proyecto directamente con `file://`, porque el portal y la página de estado leen archivos JSON mediante HTTP.
