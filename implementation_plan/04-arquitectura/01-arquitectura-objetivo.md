# 04.1 · Arquitectura objetivo

Es la foto final del sistema (al terminar V15). Cada versión construye una porción.

```mermaid
flowchart TB
    TECH["Técnico"] --> APIGW["API Gateway"]
    SUP["Supervisor"] --> APIGW
    APIGW --> AUTH["API key / JWT validation"]
    AUTH --> ROUTER{"Ruta configurada"}
    ROUTER -->|/diagnose/quick| LAMBDA["AWS Lambda + FastAPI adapter"]
    ROUTER -->|/diagnose/extended| EC2["EC2 + Docker + FastAPI"]
    subgraph CORE["Aplicación compartida"]
        GRAPH["LangGraph Orchestrator"]
        OAI["OpenAI API"]
        RAG["LangChain Retriever"]
        TG["Authorized Tool Gateway"]
        MEM["Incident Memory Gateway"]
        POLICY["Policy Engine"]
    end
    LAMBDA --> GRAPH
    EC2 --> GRAPH
    GRAPH <--> OAI
    GRAPH --> RAG
    GRAPH --> TG
    GRAPH <--> MEM
    GRAPH --> POLICY
    RAG --> VECTOR[("Supabase pgvector / failure history")]
    MEM --> INCIDENTS[("Supabase PostgreSQL / incidents")]
    TG --> MCP["MCP Client"]
    MCP --> SERVER["Maintenance MCP Server"]
    SERVER --> MOCK["Mock equipment / sensors / CMMS"]
    POLICY --> APPROVAL[("Approval requests")]
    APPROVAL --> EXEC["Authorized Action Executor"]
    EXEC --> AUDIT[("Audit events")]
    LAMBDA -.-> CW["CloudWatch"]
    EC2 -.-> CW
    GRAPH -.-> CW
    SECRET["Secrets Manager"] -.-> LAMBDA
    SECRET -.-> EC2
    IAM["IAM least privilege"] -.-> LAMBDA
    IAM -.-> EC2
```

## Cómo leer el diagrama

Léelo en **cuatro zonas**, de arriba abajo:

| Zona | Componentes | Qué hace |
|---|---|---|
| **1. Entrada** | Técnico, Supervisor, API Gateway, API key/JWT, Router | Recibe la petición, identifica al cliente y al usuario, y la envía al runtime adecuado. |
| **2. Runtime** | Lambda o EC2 | Ejecuta la misma app; solo cambia dónde corre. |
| **3. Núcleo compartido** | LangGraph, OpenAI, Retriever, Tool Gateway, Memory Gateway, Policy Engine | El "cerebro": razona, busca, consulta herramientas, recuerda y decide qué está permitido. |
| **4. Datos y acciones** | Supabase (vectores e incidentes), MCP, Approval, Executor, Audit | Donde se guardan los datos y se ejecutan (simuladas) las acciones aprobadas. |

Las líneas **punteadas** (`-.->`) son soporte transversal: CloudWatch (logs), Secrets Manager (secretos), IAM (permisos AWS).

## Los "gateways": la idea central

Cada vez que el agente toca algo externo, pasa por una **puerta controlada** en lugar de acceder directamente:

| Gateway | Protege | Verifica |
|---|---|---|
| **Tool Gateway** | Herramientas MCP | Herramienta permitida, argumentos válidos, usuario autorizado. |
| **Memory Gateway** | Incidentes en Supabase | Que el usuario pueda leer/escribir ese incidente. |
| **Action Gateway / Policy Engine** | Acciones con efecto | Política, riesgo, necesidad de aprobación. |

> Idea: el LLM *propone*; el código determinista *decide*.

## Regla de seguridad del executor

El **Action Executor** solo actúa después de verificar:

1. **Identidad** (¿quién lo pide?).
2. **Alcance** (¿sobre qué planta/equipo?).
3. **Política** (¿está permitido?).
4. **Aprobación**, cuando aplique.
5. **Idempotencia** (¿ya se ejecutó?).

Estar conectado al servidor MCP **no otorga permisos** por sí solo.
