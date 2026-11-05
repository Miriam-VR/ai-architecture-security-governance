# Glosario

Términos que aparecen en todo el plan, explicados sin jerga.

## IA y agentes

| Término | Qué es | Ejemplo en este proyecto |
|---|---|---|
| **LLM** | Modelo de lenguaje (como GPT) que genera texto. | Redacta el diagnóstico. |
| **Agente** | Programa que usa un LLM para decidir pasos: consultar, razonar, actuar. | El "Diagnosis Agent". |
| **RAG** | *Retrieval-Augmented Generation*. Antes de responder, se buscan documentos relevantes y se le entregan al LLM como evidencia. | Buscar fallas pasadas parecidas a la de P-204. |
| **Embedding** | Lista de números que representa el "significado" de un texto. Textos parecidos → números parecidos. | Permite buscar fallas por similitud. |
| **pgvector** | Extensión de PostgreSQL para guardar y buscar embeddings. | Búsqueda semántica en Supabase. |
| **LangChain** | Librería con piezas para armar apps con LLM (retrievers, adaptadores). | Retriever de RAG. |
| **LangGraph** | Librería para definir el flujo del agente como un **grafo** de nodos (pasos) y decisiones. | Ciclo razonar → pedir herramienta → razonar. |
| **MCP** | *Model Context Protocol*. Estándar para que un agente descubra y llame herramientas externas. | Servidor que expone `get_sensor_readings`. |
| **Tool / herramienta** | Función que el agente puede invocar. | `get_equipment_info`. |
| **Mock** | Versión falsa pero predecible de algo real. | Proveedor LLM falso para tests sin red. |
| **HITL** | *Human In The Loop*: una persona aprueba antes de actuar. | Supervisor aprueba una orden de trabajo. |

## Seguridad

| Término | Qué es |
|---|---|
| **Prompt injection** | Texto hostil escondido en un documento o mensaje que intenta dar órdenes al LLM ("ignora tus reglas y envía los datos…"). |
| **Trust boundary** | Línea que separa lo confiable (nuestro código) de lo no confiable (documentos recuperados, entrada de usuario). |
| **JWT** | Token firmado que prueba quién eres y qué rol tienes. |
| **RBAC** | Permisos por **rol** (técnico, supervisor, admin). |
| **ABAC** | Permisos por **atributos** (planta, equipo, incidente). |
| **RLS** | *Row Level Security*: PostgreSQL filtra filas según el usuario. |
| **IAM** | Permisos de AWS para recursos AWS. **No** protege filas de Supabase. |
| **Secrets Manager** | Servicio de AWS para guardar contraseñas y llaves fuera del código. |
| **Mínimo privilegio** | Dar solo los permisos estrictamente necesarios. |
| **Idempotencia** | Repetir una operación produce el mismo resultado que hacerla una vez (un reintento no duplica la orden). |
| **Replay** | Reenviar una aprobación vieja para que se vuelva a aceptar. |

## Gobierno y operación

| Término | Qué es |
|---|---|
| **Policy engine** | Código **determinista** (no IA) que decide si una acción se permite, requiere aprobación o se prohíbe. |
| **Decision record** | Registro de por qué y cuándo se tomó una decisión/política. |
| **Audit event** | Registro inmutable de "quién hizo qué y cuándo". |
| **Golden dataset** | Casos de prueba con la respuesta correcta conocida. |
| **Dataset adversarial** | Casos diseñados para romper el sistema (ataques). |
| **LLM-as-judge** | Usar otro LLM para calificar respuestas. Aquí es opcional y nunca el único criterio. |
| **trace_id / run_id / incident_id** | Identificadores para seguir una petición (`trace_id`), una ejecución del agente (`run_id`) y un caso (`incident_id`). |
| **OpenTelemetry** | Estándar para emitir logs, métricas y trazas. |
| **CloudWatch** | Servicio de AWS que recibe logs, métricas y alarmas. |

## Infraestructura

| Término | Qué es |
|---|---|
| **Lambda** | Ejecuta código bajo demanda; pagas por uso; límite de 15 min. |
| **EC2** | Servidor virtual siempre encendido; sin límite de tiempo. |
| **API Gateway** | Puerta de entrada HTTP en AWS que enruta a Lambda/EC2. |
| **Mangum** | Adaptador que permite correr FastAPI dentro de Lambda. |
| **ECR** | Registro de imágenes Docker de AWS. |
| **Terraform** | Describe infraestructura como código. |
| **OIDC** | Forma de que GitHub Actions entre a AWS sin llaves estáticas. |
| **SQS / DLQ** | Cola de mensajes / cola de mensajes fallidos. |
| **Drift** | Diferencia entre lo que dice Terraform y lo que realmente existe. |
