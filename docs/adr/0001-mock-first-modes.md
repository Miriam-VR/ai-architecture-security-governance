# ADR 0001 — Modos mock por defecto
**Estado:** aceptado. **Decisión:** LLM, embeddings, store, cola y secretos tienen modo `mock/memory/inline/env` (ver `.env.example`) y modo real por configuración. **Por qué:** tests reproducibles sin red ni costo (criterio 1) y sin riesgo de tocar sistemas reales. **Consecuencia:** el modo real requiere verificación aparte.
