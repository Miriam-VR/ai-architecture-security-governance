# V13 — Observabilidad y auditoría

**Problema:** Rastrear un diagnóstico de punta a punta.

## Arquitectura

```mermaid
flowchart TB
    REQ --> IDS[incident_id + run_id + trace_id]
    IDS --> LOG[Logs JSON]
    IDS --> AUD[Auditoría append-only]
    IDS --> LAT[Latencia por nodo]
```

## Archivos principales

app/observability/telemetry.py, app/governance/audit.py

## Cómo probar (modo mock, sin red)

```bash
.venv/bin/python -m pytest tests/unit/test_v13_observability.py -v
```

## Aceptación

IDs correlacionados, redacción de secretos/PII, denegaciones auditadas, OTel apagado salvo configuración.

## Riesgos / pendientes

- Datos y valores sintéticos; no son límites de seguridad industrial.
- Modo real (OpenAI / Supabase / AWS) requiere configuración en `.env.example`; no verificado en este README.
