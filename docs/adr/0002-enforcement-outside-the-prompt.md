# ADR 0002 — Las defensas viven fuera del prompt
**Estado:** aceptado. **Decisión:** autorización, allowlist de herramientas, políticas de riesgo y aprobaciones se aplican en backend (Tool Gateway, servidor MCP, executor, RLS), no en instrucciones al LLM. **Por qué:** el contenido recuperado es no confiable (prompt injection). **Pruebas:** `tests/security/test_v06_*`, `test_v07_*`, `test_v09_*`.
