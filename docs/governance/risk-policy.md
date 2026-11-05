# Política de riesgo y HITL (V11)

| Acción | Decisión |
|---|---|
| Consultar datos/diagnóstico | Permitida |
| Crear borrador de orden de trabajo | Permitida |
| Publicar orden de trabajo | Requiere aprobación de un supervisor de la misma planta (distinto del solicitante) |
| Controlar PLC / cambiar setpoints / detener maquinaria | **Prohibida para todos los roles** |

Cada cambio de política (`POST /policy`, solo admin) y cada decisión generan un *decision record* con la versión de política. Pruebas: `tests/unit/test_v11_policies.py`.
