# Modelo de amenazas (resumen)

| Amenaza | Mitigación | Prueba |
|---|---|---|
| Prompt injection en historial/manuales | Texto delimitado como dato; gateway y política deciden | test_v06 |
| Acceso cruzado PLANT-A → PLANT-B | JWT + RBAC/ABAC en endpoint, RAG, memoria, MCP; RLS | test_v07 |
| Fuga de secretos | Secrets Manager, redacción en logs/auditoría | test_v08 |
| Acción sensible sin aprobación / duplicada | Aprobación hash-ligada, idempotency key, executor no confía en la cola | test_v09 |
| Control de PLC/SCADA | Prohibido siempre por política (no relajable) | test_v11 |
| Manipulación del log de auditoría | Append-only (código y base de datos) | test_v13, test_pg_store |

Fuera de alcance: sistemas industriales reales. Políticas IAM: [iam-policies.md](iam-policies.md).
