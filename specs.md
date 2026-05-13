# Project Overview — Unified AI Agent Platform

## Goal

Build an internal platform/framework that accelerates the development, deployment, observability, and UI integration of AI agents across multiple underlying agent frameworks.

The platform should provide:

* a unified runtime interface for heterogeneous agent frameworks
* a configurable UI system
* observability and tracing
* deployment/runtime management
* secrets handling
* conversation persistence
* standardized streaming/events
* framework abstraction

The platform is intended to support multiple agent ecosystems while exposing a single coherent developer and user experience.

---

# High-Level Architecture

The system is divided into two major backend domains:

## 1. Runtime Backend (Execution Plane)

Responsible for:

* executing agents
* handling inference/runtime orchestration
* adapting multiple frameworks
* exposing unified APIs
* streaming runtime events
* tool execution
* trace generation

Supported frameworks may include:

* LangChain
* OpenAI Agents SDK
* Google ADK
* CrewAI
* AutoGen
* LlamaIndex
* future frameworks

The runtime backend should remain:

* mostly stateless
* horizontally scalable
* event-driven
* framework-agnostic at the protocol level

---

## 2. Platform Backend (Control Plane)

Responsible for:

* authentication
* RBAC
* tenant management
* conversation storage
* secret vaulting
* app registry
* YAML configuration management
* observability dashboards
* quotas/billing
* audit logs

This backend is stateful and security-sensitive.

The architecture intentionally separates:

* execution concerns
* platform/control concerns

This mirrors modern control-plane/data-plane architectures.

---

# UI System

The UI is driven by a React library that renders configurable widgets from YAML definitions.

Example responsibilities:

* widget layout
* widget types
* positioning
* app configuration
* chat interfaces
* observability panels
* runtime controls

The UI does NOT directly understand framework-specific semantics.

Instead:

* frameworks are normalized into platform concepts
* the UI consumes unified runtime events and metadata

Example:

BAD:

```yaml
langchain_memory:
```

GOOD:

```yaml
memory:
  type: conversation
```

The YAML layer represents platform abstractions, not framework abstractions.

---

# Core Architectural Philosophy

The platform should NOT tightly couple itself to:

* LangChain internals
* OpenAI-specific abstractions
* Google ADK semantics
* framework-native object models

Instead, it should define:

* a unified runtime protocol
* a unified event schema
* a standard lifecycle interface

Framework adapters translate framework-specific behavior into platform-standard events.

---

# Agent Wrapping Strategy

Agents are provided as:

* source folders
* source repositories
* packaged projects

A CLI tool wraps agents into a standardized runtime format.

Example:

```bash
platform wrap ./agent
```

The wrapper:

1. detects the framework
2. loads a manifest/config
3. generates an adapter/runtime shim
4. exposes a unified runtime protocol

---

# Agent Manifest Concept

Each agent project contains metadata describing:

* framework
* entrypoint
* callable
* runtime requirements
* capabilities

Example:

```yaml
framework: langchain
entrypoint: app/main.py
agent_callable: build_agent

capabilities:
  streaming: true
  tools: true
  state: true
```

The system should rely on:

* conventions
* manifests
* adapters

rather than brittle AST/code rewriting.

---

# Unified Runtime Protocol

The platform standardizes:

* invocation
* streaming
* tracing
* lifecycle
* metadata
* observability

The platform does NOT standardize:

* planners
* memory implementations
* orchestration logic
* internal framework abstractions

The core runtime interface resembles:

```python
class UnifiedAgentRuntime:

    async def invoke(self, request):
        ...

    async def stream(self, request):
        ...

    async def tools(self):
        ...

    async def metadata(self):
        ...

    async def health(self):
        ...
```

---

# Event-Driven Design

The platform is fundamentally event-driven.

The runtime emits standardized events instead of returning framework-native responses.

Example event types:

* message.delta
* message.completed
* tool.start
* tool.end
* trace.span
* state.update
* error
* approval.requested

The UI and observability systems consume these events generically.

This allows:

* realtime streaming
* multi-agent orchestration
* interrupts
* approvals
* tracing
* observability
* replay
* persistence
* framework interoperability

---

# Runtime Isolation

Wrapped agents should execute in:

* subprocesses
* containers
* isolated workers

NOT directly inside the core backend process.

Reasons:

* dependency isolation
* framework conflicts
* security
* crash containment
* runtime portability

---

# Long-Term Vision

The long-term product is NOT only:

* the YAML UI system
* framework wrappers

The core value is:

* a universal agent runtime protocol
* unified observability
* execution standardization
* framework interoperability
* deployment/runtime abstraction

The platform effectively acts as:

* an operating layer for AI agents
* a protocol bridge across agent ecosystems
* a control plane + runtime plane for AI systems