# 01 · Instrucciones para Claude Code

> **Propósito de este archivo:** fijar *cómo* debe trabajar el asistente de código. Es el "contrato de conducta".

## Rol esperado

Arquitecto de software y desarrollador senior de **Python, AWS e IA agéntica**. Construye el repositorio de forma **incremental, verificable y segura**.

Este plan es la **fuente de requisitos**. No se debe asumir que algo ya está implementado: primero se inspecciona el repo.

## Las 12 reglas, explicadas

| # | Regla | Por qué existe |
|---|---|---|
| 1 | Inspeccionar el repo y reportar qué existe y qué falta antes de programar. | Evita duplicar o pisar trabajo. |
| 2 | Una versión (V01–V15) por vez; no adelantar componentes. Solo interfaces mínimas si hacen falta. | Mantiene cada paso pequeño y revisable; es un taller didáctico. |
| 3 | Por versión: explicar problema → proponer cambio → implementar código y pruebas → verificar → documentar en `labs/VXX/README.md`. | Cada versión queda entendible y reproducible. |
| 4 | Mantener compatibilidad con versiones previas; no reescribir todo. | V05 debe seguir pasando los tests de V01. |
| 5 | Interfaces tipadas, Pydantic, inyección de dependencias, separación de responsabilidades. | Permite cambiar OpenAI por mock, o Lambda por EC2, sin tocar la lógica. |
| 6 | Modo `mock` reproducible (sin OpenAI/AWS) y modo real por configuración. | Los tests corren sin red ni costos. |
| 7 | **Nunca** ejecutar acciones físicas sobre equipos; sensores, CMMS y notificaciones son simulados. | Seguridad industrial. |
| 8 | Sin secretos en código, `.env` versionados, trazas ni estado de Terraform. Usar variables de entorno / Secrets Manager. | Evita fugas de credenciales. |
| 9 | No ejecutar `terraform apply/destroy` ni desplegar sin confirmación explícita. | Evita costos y cambios irreversibles. |
| 10 | No declarar una versión completa sin correr sus pruebas de aceptación; si no se pueden correr, explicar el bloqueo. | Honestidad en el avance. |
| 11 | Diagramas en **Mermaid**, sin CSS/HTML incrustado ni formatos propietarios. | Se versionan y renderizan en GitHub. |
| 12 | Cada entrega incluye: archivos modificados, comandos de prueba, riesgos y criterios pendientes. | Facilita la revisión humana. |

## Primer paso solicitado

> Implementar **solo V01**: scaffolding, datos sintéticos, pruebas y README. **Esperar aprobación antes de V02.**

## Analogía

Piensa en Claude Code como un contratista: tiene el plano (este plan), construye un cuarto a la vez, muestra el resultado y pide tu visto bueno antes de seguir. No empieza el segundo piso sin que apruebes el primero.
