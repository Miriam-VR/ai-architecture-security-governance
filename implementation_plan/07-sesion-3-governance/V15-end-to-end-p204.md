# V15 · End-to-end P-204 (30 min)

## Problema

Demostrar que **todo funciona integrado** y que los controles están activos en un escenario real (simulado).

## El escenario narrado

```mermaid
sequenceDiagram
    participant T as Técnico
    participant A as API + Auth
    participant G as Agente (LangGraph)
    participant R as RAG
    participant M as MCP
    participant P as Policy Engine
    participant S as Supervisor
    participant X as Executor + CMMS mock
    participant U as Auditoría
    T->>A: Reporta INC-204 en P-204 (PLANT-A)
    A->>G: Petición autenticada y autorizada
    G->>R: Busca fallas similares
    R-->>G: Evidencia con source_id
    G->>M: Lee sensores (86 °C, 8.4 mm/s, 2.8 bar)
    M-->>G: Observaciones
    G-->>T: Hipótesis + evidencia + verificaciones
    G->>P: Propone orden de trabajo
    P->>S: Requiere aprobación
    S->>P: Aprueba
    P->>X: Ejecutar (idempotente)
    X->>U: Registra todo
```

## Qué se construye

Un escenario completo con: incidente, evidencia citada, hipótesis, **propuesta de orden de trabajo** y **aprobación simulada**.

## Diagrama

```mermaid
flowchart TB
    TECH["Técnico P-204"] --> GW["API Gateway"]
    SUP["Supervisor"] --> GW
    GW --> AUTH["JWT + RBAC/ABAC"]
    AUTH --> RUNTIME["Lambda / EC2"]
    RUNTIME --> GRAPH["LangGraph Agent"]
    GRAPH <--> OAI["OpenAI"]
    GRAPH --> RET["LangChain RAG"]
    RET --> VDB[("Supabase failure history")]
    GRAPH --> TG["Authorized MCP Gateway"]
    TG --> MCP["Equipment / sensor MCP"]
    GRAPH <--> MEM[("Supabase incidents")]
    GRAPH --> DIAG["Evidence-based diagnosis"]
    DIAG --> RISK["Risk classification"]
    RISK --> POLICY{"Policy decision"}
    POLICY -->|Allowed| EXEC["Action executor"]
    POLICY -->|Approval required| HITL["Supervisor approval"]
    POLICY -->|Denied| REJECT["Reject"]
    HITL -->|Approved| EXEC
    HITL -->|Rejected| REJECT
    EXEC --> CMMS["Mock CMMS"]
    EXEC --> AUDIT[("Audit events")]
    REJECT --> AUDIT
    RUNTIME -.-> CW["CloudWatch"]
    GRAPH -.-> CW
    AUDIT --> REVIEW["Governance review"]
    CW --> REVIEW
```

### Cómo leerlo

Es la **suma de todo lo anterior**:

| Parte del diagrama | Viene de |
|---|---|
| Auth JWT + RBAC/ABAC | V07 |
| RAG con alcance | V02, V07 |
| MCP autorizado | V03, V08 |
| Memoria de incidentes | V04, V09 |
| Clasificación de riesgo y políticas | V11 |
| Aprobación, executor, CMMS mock | V09 |
| Auditoría y CloudWatch → **Governance review** | V13 |

El **Governance review** (al final) muestra el objetivo: que una persona pueda revisar, con evidencia, qué hizo el sistema.

## Checklist de la demo

- [ ] El diagnóstico **cita** fuentes y **distingue** observaciones de hipótesis.
- [ ] Un intento prohibido (ej. cambiar setpoint) es **rechazado**.
- [ ] La orden de trabajo **solo** se crea tras una aprobación **verificable**.
- [ ] Un reintento **no duplica** la orden.
- [ ] Todo es **rastreable** por `incident_id`, `run_id` y `trace_id`.

## Criterios de aceptación

- [ ] Flujo de punta a punta.
- [ ] Evidencia citada.
- [ ] **No** ejecución de acciones prohibidas.
- [ ] Aprobación verificable.
- [ ] Trazabilidad completa.
