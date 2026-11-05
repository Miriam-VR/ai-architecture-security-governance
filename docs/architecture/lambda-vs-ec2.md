# Lambda vs. EC2 (V05)

Ambos ejecutan el mismo núcleo FastAPI/LangGraph (`app/`); solo cambia el adaptador (`handlers/lambda_api.py` con Mangum vs. Uvicorn en Docker).

| Aspecto | Lambda + API Gateway | EC2 + Docker |
|---|---|---|
| Ruta | `/diagnose/quick` | `/diagnose/extended` |
| Costo | Por invocación; ~0 en reposo | Fijo por hora de instancia |
| Cold start | Sí (imagen en ECR) | No |
| Duración | Limitada (y 29 s en API Gateway REST por defecto) | Sin límite práctico |
| Operación | Gestionada | Parches, health checks, rollback propios |
| Conexiones DB | Usar pooler transaccional (6543) | Session pooler (5432) |

API Gateway no detecta consultas largas: el enrutamiento es explícito por ruta. Latencias medidas: ver `evaluation_report.json` (mock) y mida en AWS tras el despliegue; **no hay mediciones reales en este repo todavía**.
Prueba de paridad: `tests/integration/test_v05_runtime_parity.py`.
