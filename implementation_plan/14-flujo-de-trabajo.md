# 14 · Flujo de trabajo de Claude Code

## El ciclo por cada versión VXX

```mermaid
flowchart TB
    A["1. Leer plan y estado del repo"] --> B["2. Describir problema y arquitectura antes/después"]
    B --> C["3. Listar archivos a crear/modificar"]
    C --> D["4. Implementar el mínimo cambio viable<br/>con tipos y validación"]
    D --> E["5. Crear tests de aceptación y casos negativos"]
    E --> F["6. Ejecutar lint/tests y corregir"]
    F --> G["7. Actualizar labs/VXX/README.md y diagrama Mermaid"]
    G --> H["8. Presentar resumen, comandos y evidencia"]
    H --> I{"9. ¿Aprobado?"}
    I -->|Sí| J["Pasar a VXX+1"]
    I -->|No| D
```

## Por qué cada paso

| Paso | Motivo |
|---|---|
| 1–3 | Entender antes de tocar; evitar sorpresas. |
| 4 | Cambios pequeños = revisión fácil. |
| 5 | Incluir **casos negativos**: lo prohibido debe fallar. |
| 6 | Verificar de verdad, no suponer. |
| 7 | Cada versión deja documentación reproducible. |
| 8 | Entrega con evidencia y riesgos. |
| 9 | Punto de control humano. |

## Qué debe incluir cada entrega

- Archivos modificados.
- Comandos para probar.
- Riesgos.
- Criterios pendientes.

## Prompt de arranque recomendado

> Lee `IMPLEMENTATION_PLAN.md`. Inspecciona el repositorio y crea un plan corto para V01. Implementa únicamente el scaffolding mínimo, el proveedor mock y OpenAI, `POST /diagnose`, modelos Pydantic, `.env.example`, tests unitarios y README. No despliegues recursos AWS ni implementes V02–V15 todavía. Ejecuta las pruebas y reporta resultados y próximos pasos.

## Plantilla sugerida para `labs/VXX/README.md`

```markdown
# VXX · Título
## Problema
## Arquitectura (antes → después, Mermaid)
## Archivos creados/modificados
## Cómo probar (comandos)
## Resultados (salida de pytest, latencias, etc.)
## Riesgos y criterios pendientes
```
