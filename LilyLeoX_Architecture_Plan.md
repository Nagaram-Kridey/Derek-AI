# Derek — Autonomous Multimodal Voice Assistant
## Full System Architecture, Build Methods & Implementation Plan

**Prepared for:** Nagaram Kridey (B.Tech CSE – AI Specialisation, Python/Django Developer)
**Purpose:** Extend the existing *Derek — AI Voice Assistant* resume project into a production-grade, LLM-orchestrated, voice-first research & scheduling assistant, without discarding any existing skills — every module below is deliberately mapped onto skills already on the resume (Django REST Framework, pytest, MongoDB/PostgreSQL, Docker, Kubernetes (familiar), AWS, CI/CD, Selenium-style testing discipline, React/Node, gRPC (familiar), RAG/LLM/NLP) so the project *upgrades* the resume rather than replacing it.
**Document type:** Build specification, intended to be consumed directly by a code-generation LLM (e.g., Claude Code, Cursor, Copilot Workspace) to scaffold and implement the system section by section.

---

## Table of Contents

0. How To Use This Document
1. Executive Summary
2. Resume & ATS Alignment Map
3. Functional Requirements
4. Non-Functional Requirements & Success Metrics
5. High-Level Architecture (shared by every build method)
6. Three Build Methods (full architecture + code structure each)
   - 6.A Modular Monolith — Django REST + Celery
   - 6.B Distributed Microservices — FastAPI + gRPC + Kafka/Redis + Kubernetes
   - 6.C Agentic Multi-Agent Graph — LangGraph + Native Gemini Tool-Use
   - 6.D Comparison Matrix & Recommendation
7. Core Subsystem Deep-Dives (method-agnostic)
   - 7.1 Voice I/O — STT/TTS, Wake Word, Own-Model vs Cartesia
   - 7.2 LLM Orchestration & Gemini Integration
   - 7.3 Deep Research Engine (web + academic + verification)
   - 7.4 Document Generation (Word/PDF structured reports)
   - 7.5 Scheduling & Reminder Engine
   - 7.6 Real-Time Environment Interaction
   - 7.7 Memory & Data Layer
   - 7.8 Security, Verification & Compliance
   - 7.9 Testing & CI/CD Strategy
8. Cross-Platform Deployment Strategy
   - 8.1 Backend Cloud Deployment (AWS)
   - 8.2 Android Application
   - 8.3 Phone-Call Channel (Twilio + Gemini Live)
   - 8.4 Web Dashboard (React)
   - 8.5 Messaging Bot Channels (optional reach)
   - 8.6 Unified Integration Protocol (Gateway, MCP, Auth)
9. End-to-End Data Flow Diagrams
10. Recommended Final Repository Layout (Hybrid)
11. Implementation Roadmap (Phased)
12. Risk Register & Mitigations
13. Appendix — Config Templates, requirements.txt, .env.example

---

## 0. How To Use This Document

This file is written to be handed, section by section, to a code-generating LLM. Each subsystem (Section 7) and each build method (Section 6) contains:
- A responsibility statement (what it must do)
- A directory tree
- Skeleton code (classes/functions with real signatures and docstrings, not full production logic) that a code LLM can expand
- The external APIs/libraries it depends on

Recommended prompting pattern when handing this to a code LLM:
> "Using Section 6.A of this plan, scaffold the Django app `apps/orchestrator` exactly as specified, then implement `GeminiClient.generate()` per its docstring."

Build one subsystem at a time, run its tests (Section 7.9) before moving to the next, and only integrate cross-subsystem wiring after each is independently green.


## 1. Executive Summary

**Derek** is the successor to the existing *Derek* CLI voice assistant. It keeps the original's open-source, modular, well-tested Python philosophy and adds:

- An **LLM-first brain** (Google Gemini as the primary reasoning/orchestration model, with tool-calling, grounding, and a real-time audio Live API) instead of the earlier intent-classifier approach — while keeping the >85% intent-accuracy NLP work as a fast local fallback/offline mode.
- A **deep research engine** that plans multi-step queries, searches the open web *and* academic sources, cross-verifies every claim against ≥2 independent sources before it is allowed into a report, and auto-generates cited Word/PDF deliverables.
- A **scheduling engine** that turns natural-language requests ("remind me every Monday at 9am to check my inbox," "research competitor pricing every Friday and email me a summary") into persistent recurring jobs that can themselves trigger research or reminders.
- A **voice layer** that can run on a device-local open-source stack or a hosted low-latency API (Cartesia Sonic), decided by a documented cost/latency/quality trade-off (Section 7.1).
- **Cross-platform delivery**: a Python/FastAPI or Django backend, an Android app, a web dashboard, and an actual **phone-call channel** (you can call the assistant, or it can call you) built on Twilio + a real-time model.
- **Three independent architectural methods** for building the backend brain, so the project can be presented on a resume as "designed and evaluated 3 candidate architectures (monolith, microservices, agentic graph) before selecting a production design" — a strong systems-design signal for interviews.

## 2. Resume & ATS Alignment Map

This project must **add** keywords, not repeat ones already covered by Derek v1, SHL RAG Scraper, and the Traffic Congestion Analyzer. New ATS-relevant terms this build introduces:

| Resume skill already listed | How Derek extends it |
|---|---|
| Django, DRF, REST APIs, pytest | Method A production backend, task/reminder models, full test suite |
| LLMs, RAG, prompt engineering, Transformers | Gemini function-calling, retrieval-augmented deep research, multi-agent planning |
| Docker, Kubernetes (familiar), CI/CD, AWS | Method B containerised microservices, Helm/K8s manifests, GitHub Actions multi-service pipeline, AWS ECS/EKS deployment |
| gRPC (familiar) | Method B inter-service gRPC contracts (`.proto` definitions) |
| MongoDB, PostgreSQL, Firebase, Supabase | Task/session store, vector memory, Firebase Cloud Messaging for push reminders |
| React.js, Node.js, MERN | Companion web dashboard for transcripts/reports/schedules |
| Testing/QA discipline (Selenium/TestNG/POM) | Same rigor applied as pytest + integration + contract tests across services |

New keywords this project earns (useful for ATS parsing of future resume bullets): *Gemini API, Google Live API, agentic AI, multi-agent orchestration, LangGraph, tool-calling / function calling, retrieval-augmented generation (production), semantic scholar / arXiv API integration, citation verification, Cartesia Sonic TTS, voice cloning, wake-word detection, APScheduler/Celery Beat, Twilio programmable voice, WebSocket real-time audio streaming, Model Context Protocol (MCP), Android (Kotlin/Flutter), OAuth2/JWT, event-driven architecture, Kafka/RabbitMQ, Helm/Kubernetes manifests.*

Suggested future resume bullet (fill in real metrics once measured):
> "Architected and evaluated 3 candidate backend architectures (modular monolith, microservices, agentic multi-agent graph) for an LLM-orchestrated voice assistant; shipped a Gemini-powered deep-research engine with automatic source verification and Word/PDF report generation, plus a scheduling engine and Android + phone-call delivery channels."

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | Accept voice input (microphone, phone call, or Android app) and respond in natural speech. |
| FR-2 | Understand and execute scheduling commands: one-off reminders, recurring tasks, and "research-and-notify" jobs. |
| FR-3 | Perform deep, multi-step web research on a topic, using Gemini as the reasoning engine. |
| FR-4 | Search and cite academic papers relevant to a query (Semantic Scholar, arXiv, CrossRef). |
| FR-5 | Verify that every factual claim in a research output is backed by at least one retrievable, checkable source; flag unverified claims. |
| FR-6 | Produce actionable summaries (bullet-point "so what / next steps") in addition to full reports. |
| FR-7 | Export findings automatically as a structured Word document (.docx) and PDF, with a consistent template (title, executive summary, findings, sources/citations, appendix). |
| FR-8 | Perform real-time environment interaction: read/write local files, query system state, run permitted shell/automation actions, watch folders for changes. |
| FR-9 | Be usable from: a desktop CLI/daemon, an Android app, a web dashboard, and a real phone call (inbound or outbound). |
| FR-10 | Speak in either a licensed hosted voice (Cartesia) or a self-hosted/fine-tuned custom voice, selectable per deployment. |
| FR-11 | Persist conversation and task memory across sessions (short-term + long-term/vector memory). |
| FR-12 | Authenticate users and isolate their data (multi-user capable, even if v1 ships single-user). |

## 4. Non-Functional Requirements & Success Metrics

| Category | Target | How measured |
|---|---|---|
| Voice round-trip latency (local mic → spoken reply) | < 2.5s p50 for simple commands, < 6s for research previews | Timed integration test harness |
| STT word error rate | < 8% on clean audio (English) | Benchmark against LibriSpeech-style dev set or self-recorded set |
| TTS naturalness | MOS ≥ 4.0/5 (Cartesia) or ≥ 3.5/5 (self-hosted) | Small human eval panel / Cartesia published MOS |
| Intent/tool-routing accuracy | ≥ 90% correct tool selection on a 50-command eval set | Automated eval harness (pytest + fixtures), improving on Derek v1's 85% |
| Source verification precision | ≥ 95% of citations resolve to a live, on-topic source | Automated citation-resolution checker |
| Scheduler reliability | 0 missed jobs across 30-day soak test | Scheduler audit log analysis |
| Test coverage | ≥ 85% line coverage on core orchestrator/research/scheduler modules | pytest-cov in CI |
| Uptime (hosted backend) | ≥ 99% monthly | Health-check + uptime monitor |
| API cost ceiling | Configurable per-user daily token/API budget with hard cutoff | Cost-tracking middleware |


## 5. High-Level Architecture (shared by every build method)

Regardless of which of the 3 methods in Section 6 is used to wire things together, Derek is always composed of the same nine logical layers. Methods A/B/C differ only in *how* these layers are deployed and how they talk to each other (in-process function calls vs REST/gRPC vs an agent graph).

```
                         ┌───────────────────────────────────────────┐
                         │            CLIENT CHANNELS                │
                         │  CLI  |  Android App  |  Web Dashboard  |  │
                         │        Phone Call (Twilio)                │
                         └───────────────┬───────────────────────────┘
                                         │  WebSocket / REST / SIP-audio
                         ┌───────────────▼───────────────────────────┐
                         │        1. VOICE I/O GATEWAY                │
                         │  Wake-word • VAD • STT • TTS • audio codec │
                         └───────────────┬───────────────────────────┘
                                         │ normalized text + intent hints
                         ┌───────────────▼───────────────────────────┐
                         │     2. LLM ORCHESTRATION LAYER             │
                         │  Gemini client • system prompt • tool      │
                         │  registry • function-calling router        │
                         └───┬───────┬───────┬───────┬───────┬────────┘
                             │       │       │       │       │
                 ┌───────────▼┐ ┌────▼────┐ ┌▼───────┐ ┌────▼─────┐ ┌▼─────────┐
                 │3. RESEARCH │ │4. DOCS  │ │5. SCHED │ │6. ENV /  │ │7. MEMORY │
                 │  ENGINE    │ │ GEN     │ │ -ULER   │ │  SYSTEM  │ │ & DATA   │
                 │ web+paper  │ │ docx/pdf│ │ reminders│ │  I/O     │ │ vector + │
                 │ search +   │ │ template│ │ recurring│ │ file/os  │ │ relational│
                 │ verify     │ │ engine  │ │  jobs    │ │ actions  │ │  stores  │
                 └────────────┘ └─────────┘ └──────────┘ └──────────┘ └──────────┘
                             │       │       │       │       │
                         ┌───▼───────▼───────▼───────▼───────▼────┐
                         │   8. SECURITY, AUTH & VERIFICATION      │
                         │  API-key vault • JWT/OAuth2 • audit log │
                         └───────────────┬─────────────────────────┘
                                         │
                         ┌───────────────▼─────────────────────────┐
                         │   9. NOTIFICATION / DELIVERY LAYER       │
                         │  push (FCM) • SMS/call (Twilio) • email  │
                         │  • in-app                                │
                         └───────────────────────────────────────────┘
```

**Layer responsibilities (used verbatim by every method below):**

1. **Voice I/O Gateway** — turns raw audio into text (STT) and text/audio-tokens back into speech (TTS); owns wake-word detection and voice-activity detection (VAD).
2. **LLM Orchestration** — the "brain." Holds the system prompt, the tool/function schema, conversation state, and decides which subsystem(s) to call for a given user turn. Gemini is primary; an optional local/offline fallback model handles simple commands when there is no connectivity or budget.
3. **Research Engine** — plans a research task into sub-questions, executes web + academic search, verifies sources, and produces a structured, cited answer object.
4. **Document Generation** — turns a structured answer object into `.docx` and `.pdf` files using a fixed report template.
5. **Scheduler** — natural-language-to-cron translation, persistent job store, triggers any of layers 3/4/9 at the right time.
6. **Environment/System I/O** — sandboxed local actions: file read/write, folder watching, running whitelisted shell commands, querying system state (battery, calendar, clipboard, etc.).
7. **Memory & Data** — short-term conversation buffer, long-term vector memory (RAG over past conversations/reports), and relational storage for users/tasks/reminders/audit logs.
8. **Security & Verification** — secrets management, auth, input sanitisation, and the citation/fact verification rules that gate what Research Engine output is allowed to reach the user as "verified."
9. **Notification/Delivery** — gets a finished artifact or reminder to the user wherever they are: push notification, SMS, an outbound phone call, in-app, or email.


## 6. Three Build Methods

Each method implements all 9 layers from Section 5 but with a different deployment/communication philosophy. Build **one** of these (Method A is the recommended starting point; see 6.D), but the document specifies all three so the design space and trade-offs are documented, and so a code LLM can be pointed at whichever is chosen.

---

### 6.A — Method A: Modular Monolith (Django REST Framework + Celery)

**Philosophy:** One deployable Python service. Maximum reuse of the resume's strongest, already-proven stack (Django, DRF, pytest, MongoDB/PostgreSQL). Fastest to build, easiest to test end-to-end, easiest to run entirely on a single AWS EC2 box or even a Raspberry Pi for a home deployment. Best for an MVP and for a portfolio project that must ship in weeks, not months.

**When to choose it:** Solo developer, tight timeline, want deep Django/DRF resume reinforcement, single-user or small-team usage.

#### Architecture

```
                ┌─────────────────────────────────────────┐
                │            Django Project                │
                │  (ASGI via Daphne/Uvicorn for WebSockets) │
                └───────────────┬───────────────────────────┘
        ┌───────────────────────┼───────────────────────────┐
        │                       │                            │
 ┌──────▼──────┐        ┌───────▼────────┐          ┌────────▼────────┐
 │ apps.voice  │        │ apps.orchestrator│         │ apps.research    │
 │ STT/TTS ws  │───────▶│ Gemini client    │────────▶│ web+paper search │
 │ consumer    │        │ tool registry    │         │ verifier         │
 └─────────────┘        └───────┬─────────┘          └────────┬─────────┘
                                 │                              │
                        ┌────────▼────────┐            ┌───────▼────────┐
                        │ apps.scheduler   │            │ apps.documents  │
                        │ Celery beat jobs │            │ docx/pdf builder│
                        └────────┬────────┘            └────────┬────────┘
                                 │                              │
                        ┌────────▼──────────────────────────────▼────────┐
                        │   PostgreSQL (tasks/users) + Redis (broker) +   │
                        │   Chroma/FAISS (vector memory)                  │
                        └──────────────────────────────────────────────────┘
```

All inter-layer calls are **plain Python function/service calls** inside one process (or Celery task dispatch for anything long-running/scheduled), which is what makes this the fastest method to build and debug.

#### Directory structure

```
lily_leo_x/
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── asgi.py
│   └── celery.py
├── apps/
│   ├── accounts/                  # users, JWT auth, API-key vault
│   │   ├── models.py
│   │   ├── serializers.py
│   │   └── views.py
│   ├── voice/                     # Layer 1
│   │   ├── consumers.py           # Django Channels WebSocket consumer
│   │   ├── stt.py
│   │   ├── tts.py
│   │   └── wake_word.py
│   ├── orchestrator/              # Layer 2
│   │   ├── gemini_client.py
│   │   ├── tool_registry.py
│   │   ├── router.py
│   │   └── prompts/
│   │       └── system_prompt.md
│   ├── research/                  # Layer 3
│   │   ├── planner.py
│   │   ├── web_search.py
│   │   ├── academic_search.py
│   │   ├── verifier.py
│   │   ├── summarizer.py
│   │   └── pipeline.py
│   ├── documents/                 # Layer 4
│   │   ├── docx_builder.py
│   │   ├── pdf_builder.py
│   │   └── templates/report_template.docx
│   ├── scheduler/                 # Layer 5
│   │   ├── models.py              # ScheduledTask
│   │   ├── nl_time_parser.py
│   │   └── tasks.py               # Celery tasks
│   ├── environment/                # Layer 6
│   │   ├── file_ops.py
│   │   ├── watcher.py
│   │   └── shell_sandbox.py
│   ├── memory/                    # Layer 7
│   │   ├── vector_store.py
│   │   └── conversation.py
│   └── notifications/             # Layer 9
│       ├── push_fcm.py
│       ├── twilio_channel.py
│       └── email_channel.py
├── tests/
│   ├── test_orchestrator.py
│   ├── test_research_pipeline.py
│   ├── test_scheduler.py
│   └── test_documents.py
└── docs/
```

#### Key code skeletons

```python
# apps/orchestrator/gemini_client.py
"""Thin wrapper around the Gemini API used by every layer that needs reasoning."""
import os
from google import genai
from google.genai import types

class GeminiClient:
    """Wraps google-genai SDK; centralises model choice, safety settings, and
    tool-calling so the rest of the codebase never talks to the SDK directly.
    """

    def __init__(self, model: str = "gemini-2.5-pro", api_key: str | None = None):
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
        self.model = model

    def generate(self, prompt: str, tools: list[dict] | None = None,
                 system_instruction: str | None = None) -> types.GenerateContentResponse:
        """Single-turn or tool-augmented generation call.

        `tools` is a list of OpenAPI-style function schemas from
        `tool_registry.TOOLS`. Gemini will return a `function_call` part when
        it decides to invoke one; the orchestrator router dispatches it.
        """
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=tools)] if tools else None,
        )
        return self._client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )

    def stream_live_session(self, on_audio_chunk, on_transcript):
        """Opens a Gemini Live API (gemini-*-live) WebSocket session for
        real-time, low-latency audio-in/audio-out conversations, used by the
        phone-call and Android push-to-talk channels. See Section 8.3."""
        raise NotImplementedError("Implemented per Section 7.2 live-session spec")


# apps/orchestrator/tool_registry.py
"""Function-calling schema exposed to Gemini. Add one entry per capability."""
TOOLS = [
    {
        "name": "run_deep_research",
        "description": "Perform verified, cited, multi-source research on a topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "depth": {"type": "string", "enum": ["quick", "standard", "deep"]},
                "export_format": {"type": "string", "enum": ["docx", "pdf", "both", "none"]},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "schedule_task",
        "description": "Create a one-off or recurring reminder/research/action task.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "when_natural_language": {"type": "string"},
                "recurrence": {"type": "string", "enum": ["none", "daily", "weekly", "monthly", "cron"]},
                "cron_expression": {"type": "string"},
            },
            "required": ["description", "when_natural_language"],
        },
    },
    {
        "name": "file_or_system_action",
        "description": "Read/write a local file, list a directory, or run a whitelisted command.",
        "parameters": {"type": "object", "properties": {"action": {"type": "string"}, "args": {"type": "object"}}},
    },
]


# apps/orchestrator/router.py
"""Dispatches a Gemini function_call part to the right subsystem."""
from apps.research.pipeline import run_deep_research
from apps.scheduler.tasks import schedule_task
from apps.environment.file_ops import file_or_system_action

DISPATCH = {
    "run_deep_research": run_deep_research,
    "schedule_task": schedule_task,
    "file_or_system_action": file_or_system_action,
}

def dispatch(function_name: str, args: dict, user) -> dict:
    """Looks up and executes the tool the model asked for, then returns a
    JSON-serialisable result that gets fed back into the next Gemini turn
    as a `function_response` part."""
    handler = DISPATCH[function_name]
    return handler(user=user, **args)


# apps/scheduler/models.py
from django.db import models

class ScheduledTask(models.Model):
    RECURRENCE_CHOICES = [("none", "One-off"), ("daily", "Daily"),
                           ("weekly", "Weekly"), ("monthly", "Monthly"), ("cron", "Custom cron")]
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    description = models.TextField()
    task_type = models.CharField(max_length=32)     # "reminder" | "research" | "action"
    payload = models.JSONField(default=dict)
    run_at = models.DateTimeField()
    recurrence = models.CharField(max_length=16, choices=RECURRENCE_CHOICES, default="none")
    cron_expression = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

Testing follows the same discipline already on the resume: `pytest` + `pytest-django`, one test module per app, fixtures for a mocked `GeminiClient` so tests never hit the live API.

---

### 6.B — Method B: Distributed Microservices (FastAPI + gRPC + Kafka/Redis + Kubernetes)

**Philosophy:** Each of the 9 layers becomes its own independently deployable, independently scalable service. This is the architecture to present when the resume goal is demonstrating distributed-systems and DevOps maturity (Docker, Kubernetes, CI/CD, AWS, gRPC — all already listed as skills). Higher build cost, but the strongest "system design interview" story.

**When to choose it:** You want to showcase Kubernetes/Docker/gRPC/CI-CD depth, expect real multi-user load, or want each capability (research, scheduling, voice) to scale/deploy independently.

#### Architecture

```
        ┌────────────┐      REST/WS       ┌───────────────────┐
        │  API Gateway│◀──────────────────▶│ voice-gateway-svc  │  (FastAPI, WebSocket)
        │ (Kong/Nginx)│                    └─────────┬──────────┘
        └──────┬─────┘                                │ gRPC
               │ REST                          ┌───────▼─────────┐
       ┌───────▼────────┐    gRPC             │ orchestrator-svc  │  (FastAPI + Gemini client)
       │  auth-svc       │◀───────────────────▶│  (the "brain")    │
       └────────────────┘                     └───┬───┬───┬───┬───┘
                                                    │   │   │   │  gRPC / async events
                                    ┌───────────────┘   │   │   └───────────────┐
                            ┌───────▼──────┐  ┌─────────▼───┐  ┌────────▼──────┐  ┌──▼─────────────┐
                            │research-svc  │  │document-svc │  │scheduler-svc  │  │ env-action-svc  │
                            │(deep research│  │(docx/pdf)   │  │(Celery beat + │  │ (sandboxed local│
                            │ + verifier)  │  │             │  │ Kafka producer│  │  automation)    │
                            └──────┬───────┘  └──────┬──────┘  └──────┬────────┘  └────────┬────────┘
                                   │                 │                │                    │
                            ┌──────▼─────────────────▼────────────────▼────────────────────▼──────┐
                            │   Kafka / RabbitMQ (event bus)  +  Redis (cache/session)              │
                            │   PostgreSQL (tasks/users)  +  Vector DB (Pinecone/Chroma, managed)   │
                            └───────────────────────────────────────────────────────────────────────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │ notification-svc   │  → FCM / Twilio / Email
                                          └─────────────────────┘
```

Services talk **synchronously via gRPC** for request/response calls (e.g. orchestrator → research-svc "give me a verified answer now") and **asynchronously via Kafka events** for fire-and-forget or scheduled work (e.g. scheduler-svc publishes `task.due` → research-svc and notification-svc both subscribe).

#### Directory structure (monorepo with per-service packages)

```
lily-leo-x/
├── docker-compose.yml            # local dev: spins up all services + kafka + redis + postgres
├── k8s/
│   ├── namespace.yaml
│   ├── orchestrator-deployment.yaml
│   ├── research-deployment.yaml
│   ├── scheduler-deployment.yaml
│   ├── document-deployment.yaml
│   ├── voice-gateway-deployment.yaml
│   ├── notification-deployment.yaml
│   ├── ingress.yaml
│   └── helm/
│       └── lily-leo-x/            # Helm chart wrapping the above
├── proto/
│   ├── orchestrator.proto
│   ├── research.proto
│   └── scheduler.proto
├── services/
│   ├── voice_gateway/
│   │   ├── Dockerfile
│   │   ├── main.py               # FastAPI + WebSocket endpoint
│   │   ├── stt.py
│   │   └── tts.py
│   ├── orchestrator/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── gemini_client.py
│   │   ├── tool_registry.py
│   │   └── grpc_clients/          # generated stubs from proto/
│   ├── research/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── grpc_server.py
│   │   ├── planner.py
│   │   ├── web_search.py
│   │   ├── academic_search.py
│   │   └── verifier.py
│   ├── document/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── docx_builder.py
│   │   └── pdf_builder.py
│   ├── scheduler/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── celery_app.py
│   │   └── kafka_producer.py
│   ├── env_action/
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── notification/
│   │   ├── Dockerfile
│   │   └── main.py
│   └── shared_libs/                # published as an internal pip package
│       ├── auth/
│       ├── logging/
│       └── schemas/
├── .github/workflows/
│   ├── ci.yml                     # lint + pytest per service on PR
│   └── cd.yml                     # build+push images, helm upgrade on merge to main
└── tests/
    ├── unit/                      # per-service, mocked network boundaries
    └── integration/               # docker-compose based contract tests
```

#### Key code skeletons

```protobuf
// proto/research.proto
syntax = "proto3";
package lilyleox.research;

service ResearchService {
  rpc RunDeepResearch (ResearchRequest) returns (ResearchResult);
}

message ResearchRequest {
  string topic = 1;
  string depth = 2;            // quick | standard | deep
  string user_id = 3;
}

message Source {
  string url = 1;
  string title = 2;
  string publisher = 3;
  bool verified = 4;
}

message ResearchResult {
  string executive_summary = 1;
  repeated string key_findings = 2;
  repeated string actionable_next_steps = 3;
  repeated Source sources = 4;
  float verification_confidence = 5;
}
```

```python
# services/orchestrator/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from .gemini_client import GeminiClient
from .grpc_clients.research_client import ResearchClient
from .grpc_clients.scheduler_client import SchedulerClient

app = FastAPI(title="orchestrator-svc")
gemini = GeminiClient()
research = ResearchClient()
scheduler = SchedulerClient()

class Turn(BaseModel):
    user_id: str
    text: str
    session_id: str

@app.post("/v1/turn")
async def handle_turn(turn: Turn):
    """Single conversational turn: run Gemini with tools, dispatch any
    function calls to the appropriate downstream gRPC service, and return
    the final natural-language reply for the voice-gateway to speak."""
    response = gemini.generate(turn.text, tools=TOOLS)
    for part in response.candidates[0].content.parts:
        if part.function_call:
            if part.function_call.name == "run_deep_research":
                result = await research.RunDeepResearch(**part.function_call.args)
            elif part.function_call.name == "schedule_task":
                result = await scheduler.CreateTask(**part.function_call.args)
            # feed result back to Gemini for a final natural-language answer
            response = gemini.generate_with_function_result(part, result)
    return {"reply_text": response.text, "session_id": turn.session_id}
```

```yaml
# k8s/orchestrator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestrator-svc
  namespace: lily-leo-x
spec:
  replicas: 2
  selector:
    matchLabels: {app: orchestrator-svc}
  template:
    metadata:
      labels: {app: orchestrator-svc}
    spec:
      containers:
        - name: orchestrator-svc
          image: <ecr-repo>/lily-leo-x-orchestrator:latest
          ports: [{containerPort: 8000}]
          envFrom:
            - secretRef: {name: lily-leo-x-secrets}
          resources:
            requests: {cpu: "250m", memory: "256Mi"}
            limits: {cpu: "1", memory: "512Mi"}
          readinessProbe:
            httpGet: {path: /healthz, port: 8000}
            initialDelaySeconds: 5
```

---

### 6.C — Method C: Agentic Multi-Agent Graph (LangGraph + Native Gemini Tool-Use)

**Philosophy:** The "brain" itself is not a single call-and-respond function but a **graph of cooperating agents** (planner → researcher(s) → verifier → writer → critic loop), which is the current state-of-the-art pattern for autonomous deep research. This method is deployable inside either Method A or Method B as the implementation of the orchestrator layer — it is an *internal architecture for Layer 2 + Layer 3 combined*, not a full replacement for the rest of the system.

**When to choose it:** You want the assistant to genuinely plan multi-step research autonomously (rather than one Gemini call with tools), want a self-critique/verification loop before anything is reported as fact, and want to demonstrate agentic-AI systems design specifically (a fast-growing, high-signal ATS keyword area).

#### Architecture (agent graph)

```
                         ┌────────────────────────────────────┐
                         │              PLANNER AGENT           │
                         │ decomposes the user goal into        │
                         │ sub-questions + a research plan       │
                         └───────────────────┬───────────────────┘
                                             │ plan: [sub_q1, sub_q2, ...]
                         ┌───────────────────▼───────────────────┐
                         │           RESEARCHER AGENT(S)          │
                         │  (fan-out, one per sub-question)       │
                         │  tools: web_search, academic_search,   │
                         │         fetch_url, read_local_file     │
                         └───────────────────┬───────────────────┘
                                             │ draft findings + raw sources
                         ┌───────────────────▼───────────────────┐
                         │             VERIFIER AGENT              │
                         │ cross-checks each claim against ≥2      │
                         │ independent sources; drops/flags        │
                         │ anything unverifiable                   │
                         └───────────────────┬───────────────────┘
                                 pass │             │ fail (needs more evidence)
                         ┌───────────▼───────┐     │
                         │   WRITER AGENT      │◀────┘ (loops back to Researcher)
                         │ builds structured   │
                         │ report + summary    │
                         └───────────┬───────────┘
                                     │
                         ┌───────────▼───────────┐
                         │   CRITIC AGENT (opt.)   │  reviews clarity/completeness,
                         │   sends back to Writer  │  max 2 revision loops
                         └───────────┬───────────┘
                                     │
                              final ResearchResult
                                     │
                     ┌───────────────▼───────────────┐
                     │  SCHEDULER AGENT (parallel)     │  owns recurring/one-off jobs,
                     │  can itself invoke the graph     │  re-entering at Planner
                     └─────────────────────────────────┘
```

#### Directory structure

```
lily_leo_x_agents/
├── requirements.txt          # langgraph, langchain-google-genai, google-genai
├── main.py                   # CLI/daemon entrypoint
├── graph.py                  # builds the StateGraph wiring all agents
├── state.py                  # TypedDict shared state passed between nodes
├── agents/
│   ├── planner_agent.py
│   ├── researcher_agent.py
│   ├── verifier_agent.py
│   ├── writer_agent.py
│   ├── critic_agent.py
│   └── scheduler_agent.py
├── tools/
│   ├── web_search_tool.py
│   ├── academic_search_tool.py
│   ├── url_fetch_tool.py
│   ├── file_ops_tool.py
│   └── document_export_tool.py
├── memory/
│   ├── vector_memory.py
│   └── checkpointer.py       # LangGraph persistent checkpoints (resumable runs)
└── tests/
    ├── test_graph_end_to_end.py
    └── test_verifier_agent.py
```

#### Key code skeletons

```python
# state.py
from typing import TypedDict, Literal

class Source(TypedDict):
    url: str
    title: str
    verified: bool

class ResearchState(TypedDict):
    goal: str
    sub_questions: list[str]
    findings: list[dict]          # {sub_question, answer, sources: list[Source]}
    verification_status: Literal["pending", "passed", "needs_more_evidence"]
    revision_count: int
    final_report: dict | None


# agents/planner_agent.py
from state import ResearchState
from google import genai

def planner_agent(state: ResearchState, llm: genai.Client) -> ResearchState:
    """Breaks the user's research goal into 3-6 independently answerable
    sub-questions, ordered so that foundational facts are researched first."""
    prompt = (f"Decompose this research goal into 3-6 sub-questions, most "
              f"foundational first. Goal: {state['goal']}")
    resp = llm.models.generate_content(model="gemini-2.5-pro", contents=prompt)
    state["sub_questions"] = _parse_bullet_list(resp.text)
    return state


# agents/verifier_agent.py
def verifier_agent(state: ResearchState) -> ResearchState:
    """For every finding, requires >=2 independent, resolvable sources that
    corroborate the claim. Findings failing this are marked unverified and
    routed back to the researcher for another pass (up to 2 retries)."""
    all_verified = True
    for finding in state["findings"]:
        independent_domains = {s["url"].split("/")[2] for s in finding["sources"]}
        finding["sources"] = [dict(s, verified=len(independent_domains) >= 2) for s in finding["sources"]]
        if len(independent_domains) < 2:
            all_verified = False
    state["verification_status"] = "passed" if all_verified else "needs_more_evidence"
    return state


# graph.py
from langgraph.graph import StateGraph, END
from state import ResearchState
from agents.planner_agent import planner_agent
from agents.researcher_agent import researcher_agent
from agents.verifier_agent import verifier_agent
from agents.writer_agent import writer_agent

def build_graph():
    g = StateGraph(ResearchState)
    g.add_node("planner", planner_agent)
    g.add_node("researcher", researcher_agent)
    g.add_node("verifier", verifier_agent)
    g.add_node("writer", writer_agent)

    g.set_entry_point("planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", "verifier")
    g.add_conditional_edges(
        "verifier",
        lambda s: "writer" if s["verification_status"] == "passed" or s["revision_count"] >= 2 else "researcher",
        {"writer": "writer", "researcher": "researcher"},
    )
    g.add_edge("writer", END)
    return g.compile()
```

---

### 6.D — Comparison Matrix & Recommendation

| Criterion | A. Modular Monolith | B. Microservices | C. Agentic Graph |
|---|---|---|---|
| Time to first working demo | Fastest (days) | Slowest (weeks) | Medium (days–1 week) |
| Matches strongest existing resume skill | Very high (Django/DRF/pytest) | High (Docker/K8s/gRPC/CI-CD) | Medium (new agentic-AI signal) |
| Scalability | Vertical only | Horizontal, per-service | Depends on host method (A or B) |
| Research quality/autonomy | Good (single-pass + tools) | Good | Best (multi-step, self-verifying) |
| Operational complexity | Low | High | Low–Medium (it's a library, not infra) |
| Best resume story | "Shipped an LLM-orchestrated assistant end-to-end" | "Designed a distributed, containerised, gRPC-based AI platform" | "Designed an autonomous multi-agent research system with a verification loop" |

**Recommendation:** Build **Method A** first as the deployable product (fast, reuses strongest skills, ships something real). Implement its `apps/orchestrator` internals using the **Method C** agent graph instead of a single Gemini call — this gets the autonomous, self-verifying research quality without the infra overhead of Method B. Document Method B fully (as done above) and optionally migrate 1-2 hot services (research-svc, scheduler-svc) into it later as a "v2 scale-out" story — this progression (monolith → agentic core → selective microservice extraction) is itself an excellent systems-design narrative for interviews and resumes.


## 7. Core Subsystem Deep-Dives (method-agnostic)

These specs apply no matter which of Methods A/B/C is chosen — only the file location changes (a Django app, a microservice, or a LangGraph tool).

### 7.1 Voice I/O — STT/TTS, Wake Word, Own-Model vs Cartesia

**Requirement mapping:** FR-1, FR-10.

**Speech-to-Text (STT) options:**

| Option | Latency | Accuracy | Cost | Offline? |
|---|---|---|---|---|
| Local Whisper (`faster-whisper`, small/medium) | Medium | Good | Free (compute only) | Yes |
| Gemini Live API native audio transcription | Very low (streamed) | Very good | Per-token/API | No |
| Cloud STT (Google Cloud Speech-to-Text) | Low | Very good | Per-minute | No |

**Text-to-Speech (TTS) decision framework — "own model vs Cartesia":**

Build a small internal voice fine-tuned only if all three hold: (1) you have ≥30 minutes of clean, consented source audio, (2) offline/on-device operation is a hard requirement, (3) you can accept training/inference engineering overhead (GPU, model serving). Approach: `Coqui XTTS-v2` or `F5-TTS` for few-shot voice cloning, fine-tuned/served locally with `onnxruntime` or a small `Triton`/`fastapi` inference server.

Otherwise — the default recommendation — use **Cartesia's `sonic-3` model** via their TTS API: instant, few-seconds voice cloning through the `Clone Voice` endpoint, ~90-130ms time-to-first-audio streaming latency, and native WebSocket/SSE/bytes endpoints that fit a real-time voice assistant far better than a self-hosted model without dedicated GPU infrastructure. Always use **voice IDs** (not raw embeddings — Cartesia deprecated embedding-based calls) and pin an explicit `Cartesia-Version` header for stability.

```python
# apps/voice/tts.py
from cartesia import Cartesia
import os

class CartesiaTTS:
    """Hosted low-latency TTS. Falls back to a local Coqui model if
    CARTESIA_API_KEY is unset (see LocalTTS below) so the assistant still
    works fully offline / at zero API cost during development."""

    def __init__(self, voice_id: str, model_id: str = "sonic-3"):
        self.client = Cartesia(api_key=os.environ["CARTESIA_API_KEY"])
        self.voice_id = voice_id
        self.model_id = model_id

    def speak_stream(self, text: str):
        """Yields raw PCM audio chunks for immediate playback/streaming to
        the client (Android app, phone call, or local speaker)."""
        return self.client.tts.sse(
            model_id=self.model_id,
            transcript=text,
            voice={"mode": "id", "id": self.voice_id},
            output_format={"container": "raw", "encoding": "pcm_s16le", "sample_rate": 16000},
        )

    def clone_voice_from_sample(self, wav_path: str, name: str) -> str:
        """One-time setup: clone a consented voice sample (3-10s of audio)
        and return a reusable voice_id."""
        with open(wav_path, "rb") as f:
            voice = self.client.voices.clone(clip=f, language="en", name=name, mode="similarity")
        return voice.id


# apps/voice/wake_word.py
"""Wake-word detection runs fully on-device (Porcupine/openWakeWord) so the
assistant is not always streaming audio to any cloud API."""
class WakeWordDetector:
    def __init__(self, keyword: str = "hey derek"):
        ...
    def listen(self, on_wake):
        """Blocks on the microphone stream; calls on_wake() when the
        keyword is detected, then hands control to the STT pipeline."""
```

**Ethical/consent note (documented for the build, not just the code):** any voice cloned via Cartesia's `Clone Voice` API must be the user's own voice or a voice they have explicit rights/consent to use; store consent confirmation alongside the `voice_id` in the database.

### 7.2 LLM Orchestration & Gemini Integration

**Requirement mapping:** FR-1–FR-9 (Gemini is the reasoning layer behind almost everything).

Two Gemini integration modes are used side by side:

1. **Turn-based (`generate_content` + function-calling)** — used for text-driven flows: scheduling a task, answering a quick question, kicking off research. This is the mode shown in the `GeminiClient.generate()` skeleton in Section 6.A.
2. **Real-time Live session (`gemini-*-live` family, e.g. `gemini-3.8-live`)** — a stateful, bidirectional **WebSocket** connection that streams raw 16-bit PCM audio in and receives streamed audio+text out, with built-in barge-in (the user can interrupt), voice-activity detection, native audio transcription, function calling (synchronous or async/non-blocking), and Google Search grounding. This is the mode used for the phone-call channel (Section 8.3) and for a natural "always-listening" conversational mode in the Android app, because it removes the STT→LLM→TTS round-trip latency of the turn-based mode.

```python
# apps/orchestrator/live_session.py
"""Real-time voice conversation via the Gemini Live API.
Always re-check the current model name/capabilities in Google's docs before
deployment, since Live API model names are updated frequently (e.g. the
family has moved from gemini-2.5-flash-native-audio-* to gemini-3.x-live).
"""
import asyncio
from google import genai
from google.genai import types

LIVE_MODEL = "gemini-3.8-live"   # verify current model string at build time

class LiveVoiceSession:
    def __init__(self, api_key: str, tools: list[dict], system_instruction: str):
        self.client = genai.Client(api_key=api_key)
        self.tools = tools
        self.system_instruction = system_instruction

    async def run(self, audio_in_stream, audio_out_sink, on_function_call):
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=self.system_instruction,
            tools=[types.Tool(function_declarations=self.tools)],
        )
        async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            async def send_audio():
                async for chunk in audio_in_stream:
                    await session.send_realtime_input(audio=chunk)
            async def receive():
                async for response in session.receive():
                    if response.data:               # audio bytes
                        await audio_out_sink(response.data)
                    if response.tool_call:           # async function call
                        result = await on_function_call(response.tool_call)
                        await session.send_tool_response(function_responses=[result])
            await asyncio.gather(send_audio(), receive())
```

**System prompt design** lives in `prompts/system_prompt.md` (kept out of code so it can be iterated on without a redeploy) and encodes: assistant persona, the rule that *no unverified claim may be presented as fact* (ties to 7.3/7.8), tool-use policy (prefer `run_deep_research` over answering from memory for anything time-sensitive), and a strict refusal policy for destructive environment actions without explicit confirmation.

### 7.3 Deep Research Engine

**Requirement mapping:** FR-3, FR-4, FR-5, FR-6.

Pipeline stages (implemented as either plain functions — Method A/B — or graph nodes — Method C):

1. **Query decomposition** — LLM breaks the topic into sub-questions (Planner).
2. **Web search** — a pluggable search backend (Tavily, SerpAPI, or Gemini's built-in Search grounding tool) returns candidate sources per sub-question.
3. **Academic/citation search** — queries **Semantic Scholar Graph API** (`https://api.semanticscholar.org/graph/v1`), **arXiv API** (`http://export.arxiv.org/api/query`), and **CrossRef** (`https://api.crossref.org/works`) for peer-reviewed backing where the topic is technical/scientific.
4. **Source verification** — every claim must resolve to ≥2 independent domains (Section 6.C `verifier_agent`); domain-authority heuristics (prefer `.gov`, `.edu`, major publishers, peer-reviewed venues) feed a confidence score; unresolvable/unreachable URLs are dropped, not guessed.
5. **Summarisation** — map-reduce: each sub-question's findings are summarised individually, then combined into an executive summary + "actionable next steps" list (FR-6).
6. **Export** — handed to the Document Generation subsystem (7.4).

```python
# apps/research/academic_search.py
import httpx

SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/search"
ARXIV = "http://export.arxiv.org/api/query"

async def search_semantic_scholar(query: str, limit: int = 5) -> list[dict]:
    """Returns [{title, authors, year, url, abstract, citation_count}, ...]."""
    params = {"query": query, "limit": limit, "fields": "title,authors,year,url,abstract,citationCount"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(SEMANTIC_SCHOLAR, params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

async def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Parses the arXiv Atom feed into a list of paper dicts."""
    params = {"search_query": f"all:{query}", "start": 0, "max_results": max_results}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(ARXIV, params=params)
        return _parse_arxiv_atom(resp.text)


# apps/research/verifier.py
async def verify_claim(claim: str, candidate_sources: list[dict]) -> dict:
    """Attempts to fetch each candidate source and checks (a) it is reachable,
    (b) its content is topically related to the claim (embedding similarity
    threshold), and (c) at least 2 independent domains corroborate it.
    Returns {verified: bool, confidence: float, sources: [...]}"""
```

### 7.4 Document Generation (Word/PDF structured reports)

**Requirement mapping:** FR-6, FR-7. Mirrors a "deep-dive" style deliverable: Title Page → Executive Summary → Key Findings → Actionable Next Steps → Detailed Analysis → Sources & Citations → Appendix.

```python
# apps/documents/docx_builder.py
from docx import Document
from docx.shared import Pt

def build_research_docx(result: dict, output_path: str) -> str:
    """result: {title, executive_summary, key_findings: [...], next_steps: [...],
    detailed_sections: [{heading, body}], sources: [{title, url, publisher}]}"""
    doc = Document()
    doc.add_heading(result["title"], level=0)
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(result["executive_summary"])

    doc.add_heading("Key Findings", level=1)
    for finding in result["key_findings"]:
        doc.add_paragraph(finding, style="List Bullet")

    doc.add_heading("Actionable Next Steps", level=1)
    for step in result["next_steps"]:
        doc.add_paragraph(step, style="List Number")

    for section in result["detailed_sections"]:
        doc.add_heading(section["heading"], level=2)
        doc.add_paragraph(section["body"])

    doc.add_heading("Sources & Citations", level=1)
    for i, src in enumerate(result["sources"], start=1):
        doc.add_paragraph(f"[{i}] {src['title']} — {src['publisher']} ({src['url']})")

    doc.save(output_path)
    return output_path


# apps/documents/pdf_builder.py
"""Reuses the same `result` schema. Two supported strategies:
1. Render the same content to HTML (Jinja2 template) then convert with
   WeasyPrint (pure-Python, good typography, no headless browser needed).
2. If the .docx is already built, convert it via LibreOffice headless
   (`soffice --headless --convert-to pdf`) for perfect visual parity.
Prefer (1) for programmatic control over layout, (2) for guaranteed
docx/pdf parity when both are requested (export_format="both")."""
```

### 7.5 Scheduling & Reminder Engine

**Requirement mapping:** FR-2.

- **Natural-language time parsing**: `dateparser` + a custom recurrence grammar ("every weekday at 8am", "the first Monday of each month") normalised into either a concrete `datetime` (one-off) or a `cron_expression` (recurring), stored on `ScheduledTask` (Section 6.A model).
- **Execution engine**: Celery Beat (Method A/C host) or a Kafka-driven cron dispatcher (Method B) polls due tasks and re-enters the orchestrator with the stored `task_type`/`payload` — a scheduled task is literally "replay this tool call now," which is why the scheduler never needs to know about voice/research/documents internally.
- **Idempotency & missed-run recovery**: every dispatch is recorded with a `last_run_at` and a dispatch-id so a crash/restart cannot double-fire or silently drop a job (soak-tested per the NFR in Section 4).

```python
# apps/scheduler/nl_time_parser.py
import dateparser
from croniter import croniter

def parse_schedule(natural_language: str, recurrence: str) -> dict:
    """Returns {run_at: datetime, cron_expression: str|None}.
    For recurrence != 'none', converts common phrases to a cron expression
    (e.g. 'weekly' + 'every Monday at 9am' -> '0 9 * * 1')."""
    ...

# apps/scheduler/tasks.py
from celery import shared_task
from apps.orchestrator.router import dispatch

@shared_task
def run_due_task(task_id: int):
    """Celery Beat calls this at run_at / on each cron tick. Re-enters the
    orchestrator dispatch table exactly as if the user had just asked for
    this action by voice."""
    task = ScheduledTask.objects.get(id=task_id)
    result = dispatch(task.task_type, task.payload, user=task.user)
    task.last_run_at = timezone.now()
    task.save(update_fields=["last_run_at"])
    notify_user.delay(task.user_id, result)
```

### 7.6 Real-Time Environment Interaction

**Requirement mapping:** FR-8.

All local/system actions go through a **single sandboxed gateway** — nothing in the orchestrator or research layers is allowed direct filesystem/subprocess access — so every action is auditable and deny-by-default.

```python
# apps/environment/shell_sandbox.py
ALLOWLISTED_COMMANDS = {"df", "battery_status", "list_calendar_events"}

def run_whitelisted_action(action: str, args: dict, user) -> dict:
    """Refuses anything not in ALLOWLISTED_COMMANDS. Destructive or
    filesystem-write actions additionally require a `confirm=True` flag
    that the orchestrator can only set after the LLM has explicitly
    surfaced a confirmation question to the user and received 'yes'."""
    if action not in ALLOWLISTED_COMMANDS:
        raise PermissionError(f"Action '{action}' is not allowlisted")
    ...

# apps/environment/watcher.py
"""watchdog-based folder watcher: lets the user say 'tell me when a new
invoice lands in ~/Downloads' — registers a watch that, on match, re-enters
the orchestrator the same way a scheduled task does."""
```

### 7.7 Memory & Data Layer

**Requirement mapping:** FR-11.

| Store | Purpose | Tech |
|---|---|---|
| Relational | Users, ScheduledTasks, audit log, consent records | PostgreSQL (prod) / SQLite (dev) — reuses SQL modelling skill already on resume |
| Cache/session/broker | Celery broker, short-term conversation buffer | Redis |
| Vector memory | Long-term RAG over past conversations & past research reports, so "what did we find out about X last month?" works | Chroma (self-hosted, free) or Pinecone (managed, for the microservices method) |

```python
# apps/memory/vector_store.py
import chromadb

class LongTermMemory:
    def __init__(self, path: str = "./chroma_data"):
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection("lily_leo_x_memory")

    def store(self, doc_id: str, text: str, metadata: dict):
        self.collection.add(ids=[doc_id], documents=[text], metadatas=[metadata])

    def recall(self, query: str, n_results: int = 5) -> list[dict]:
        """Semantic search over past conversations/reports for RAG-style
        recall inside a new conversation turn."""
        return self.collection.query(query_texts=[query], n_results=n_results)
```

### 7.8 Security, Verification & Compliance

**Requirement mapping:** FR-5, FR-12, and the NFR cost ceiling.

- **Secrets**: `GEMINI_API_KEY`, `CARTESIA_API_KEY`, `TWILIO_*`, DB credentials never hard-coded; loaded from environment/`.env` locally and from **AWS Secrets Manager** in production (ties to AWS cert).
- **Auth**: JWT (`djangorestframework-simplejwt` for Method A, `python-jose` for Method B) for API/app clients; OAuth2 for any third-party account linking (e.g. calendar sync).
- **Input sanitisation**: every user-supplied string that reaches a shell/file action passes through an allowlist validator (7.6); every LLM-facing prompt is templated (never raw string concatenation of untrusted input into system instructions).
- **Verification gate**: the Research Engine (7.3) is not allowed to mark a finding "verified" in the exported document unless it passed the ≥2-independent-source rule; unverified claims are explicitly labelled "unverified — treat as a lead, not a fact" rather than silently omitted.
- **Cost control**: a per-user daily token/request budget tracked in Redis, enforced by orchestrator middleware, with a hard stop + user notification when exceeded.
- **Audit log**: every tool dispatch (Section 6.A `router.dispatch`) is logged with user, timestamp, tool name, and args for later review.

### 7.9 Testing & CI/CD Strategy

Directly extends the testing discipline already proven in the internship experience (Selenium/TestNG/POM → pytest/mocks here).

| Layer | Test type | Tooling |
|---|---|---|
| Orchestrator/tool routing | Unit, with `GeminiClient` mocked | `pytest`, `unittest.mock` |
| Research pipeline | Unit (per stage) + golden-file integration test on a fixed topic | `pytest`, VCR-style HTTP cassette recording (`vcrpy`) so tests don't hit live APIs |
| Scheduler | Time-travel tests (freeze time, assert correct dispatch) | `pytest`, `freezegun` |
| Document generation | Snapshot tests on generated docx/pdf structure (not pixel-diff) | `pytest`, `python-docx` introspection |
| Voice I/O | Contract tests against recorded sample audio | `pytest` fixtures with sample `.wav` files |
| End-to-end (Method B only) | Service contract tests via docker-compose | `pytest` + `testcontainers` |
| CI | Lint (`ruff`/`flake8`) + type-check (`mypy`) + full pytest suite + coverage gate (≥85%) on every PR | GitHub Actions |
| CD | Build & push Docker images, run `docker-compose` smoke test, deploy (EC2/ECS for A, Helm upgrade to EKS for B) on merge to `main` | GitHub Actions + AWS |


## 8. Cross-Platform Deployment Strategy

### 8.1 Backend Cloud Deployment (AWS)

- **Method A (monolith):** single Docker image deployed to an EC2 instance (or AWS App Runner for less ops overhead) behind an Application Load Balancer; PostgreSQL on RDS; Redis on ElastiCache; static/media on S3. CI/CD via GitHub Actions → ECR → EC2/App Runner deploy.
- **Method B (microservices):** each service is its own image in ECR; deployed to **EKS** (Kubernetes) using the Helm chart in `k8s/helm/lily-leo-x`; Kafka via **Amazon MSK** (or self-hosted Redpanda for lower cost); RDS + ElastiCache shared across services; Secrets Manager for all API keys.
- Both: **CloudWatch** for logs/metrics, **AWS Secrets Manager** for `GEMINI_API_KEY`/`CARTESIA_API_KEY`/`TWILIO_*`, and a documented cost-guardrail (budget alarms) given LLM/TTS API usage is the main variable cost.

### 8.2 Android Application

Two viable client architectures, pick based on time budget:

1. **Native/Kotlin (recommended for resume depth if time allows):** Android app using `MediaRecorder`/`AudioRecord` for mic capture, a foreground service for wake-word listening and background reminders, Jetpack Compose UI for a chat/report view, Retrofit/OkHttp for REST calls to the backend, and a raw WebSocket client (OkHttp WebSocket or a Gemini Live client) for real-time voice turns. Push notifications for reminders via **Firebase Cloud Messaging (FCM)**.
2. **Cross-platform (Flutter or React Native, recommended for speed):** reuses the React/JS skill already on the resume (React Native) or benefits from Flutter's stronger audio-streaming plugin ecosystem; talks to the exact same backend REST/WebSocket API as the native option, so backend code is shared regardless of which client is chosen.

```
android_app/
├── app/src/main/java/.../
│   ├── voice/WakeWordService.kt        # foreground service, on-device wake word
│   ├── voice/LiveVoiceClient.kt        # WebSocket bridge to orchestrator/voice-gateway
│   ├── ui/ChatScreen.kt                # Jetpack Compose conversation view
│   ├── ui/ReportsScreen.kt             # lists generated docx/pdf reports
│   ├── ui/ScheduleScreen.kt            # create/view scheduled tasks
│   └── notifications/FcmService.kt     # receives reminder pushes
└── app/build.gradle.kts
```

The Android app never talks to Gemini/Cartesia directly — it always goes through the backend, so API keys never ship inside the APK (a security requirement, not just a design preference).

### 8.3 Phone-Call Channel (Twilio + Gemini Live)

This is what makes the assistant reachable "through phone calls" as requested:

1. A Twilio phone number is configured with a **Voice webhook** pointing at the backend (`voice-gateway` in Method A/B).
2. On an inbound call, Twilio requests TwiML; the backend responds with a `<Connect><Stream>` (Twilio **Media Streams**) directive, which opens a bidirectional WebSocket carrying raw call audio (μ-law, 8kHz) to the backend.
3. The backend transcodes that audio and bridges it into a **Gemini Live** session (Section 7.2 `LiveVoiceSession`), streaming Gemini's audio replies back down the same Media Stream to the caller — giving a real-time, interruptible phone conversation with the assistant.
4. **Outbound** calls (e.g. "call me when the research is done" or a spoken reminder) are placed via the Twilio REST API (`client.calls.create(...)`) with the same TwiML/Media-Stream bridge.
5. Fallback for cost/simplicity: a turn-based mode using Twilio's built-in `<Gather input="speech">` (Twilio's own STT) → orchestrator turn-based call → Twilio `<Say>`/`<Play>` (Cartesia audio) — simpler to build first, upgrade to full Media-Streams + Live API bridging once the turn-based path works end-to-end.

```python
# services/voice_gateway/twilio_bridge.py  (sketch)
from fastapi import FastAPI, WebSocket
from twilio.twiml.voice_response import VoiceResponse, Connect

app = FastAPI()

@app.post("/twilio/voice")
async def incoming_call():
    resp = VoiceResponse()
    connect = Connect()
    connect.stream(url="wss://<your-domain>/twilio/media-stream")
    resp.append(connect)
    return Response(content=str(resp), media_type="application/xml")

@app.websocket("/twilio/media-stream")
async def media_stream(ws: WebSocket):
    """Bridges Twilio's mu-law/8kHz audio frames <-> a Gemini LiveVoiceSession,
    transcoding sample rate/encoding in both directions."""
    await ws.accept()
    ...
```

### 8.4 Web Dashboard (React)

A companion React (or Next.js) app — reusing the MERN-stack skill already on the resume — for the parts that are easier on a screen than by voice: browsing/downloading generated `.docx`/`.pdf` reports, managing scheduled tasks visually, reviewing conversation history, and configuring voice/API-key settings. Talks to the same backend REST API as the Android app (no duplicate business logic).

### 8.5 Messaging Bot Channels (optional extra reach)

Low-effort additional channels, since they reuse the same orchestrator "turn" endpoint: a **Telegram bot** (voice-note in → transcribe → orchestrator → TTS reply out, plus native document sending for reports) and/or a **WhatsApp Business API** integration. These are good "nice to have, low cost, high visible reach" additions once the core is stable.

### 8.6 Unified Integration Protocol (Gateway, MCP, Auth)

- **API Gateway**: a single entry point (Nginx/Kong for Method B, Django's own URLconf for Method A) fronting REST (task/report CRUD) and WebSocket (voice/live) traffic; consistent JSON error envelope and versioning (`/v1/...`) across every channel (Android, web, Twilio bridge).
- **Auth**: JWT bearer tokens for the Android/web clients; a signed webhook-validation scheme for Twilio's inbound requests; OAuth2 if/when third-party calendar or email accounts are linked.
- **Tool/agent interoperability protocol**: define every internal tool (Section 6.A `tool_registry.TOOLS`) using the same JSON-Schema-based function-declaration format Gemini expects. Optionally expose these same tools over the **Model Context Protocol (MCP)** so the research/scheduling/document tools can also be driven by other MCP-compatible clients (e.g. Claude Desktop or Claude Code during development/debugging) — this is both a genuine engineering convenience (uniform tool interface) and a strong, current ATS keyword.
- **Internal service contracts (Method B only)**: `.proto` files in `proto/` are the single source of truth; gRPC stubs are generated in CI so services never drift from the contract silently.


## 9. End-to-End Data Flow Diagrams

**A. Voice command flow ("remind me to call mom tomorrow at 6pm")**
```
Mic/Phone/App → Voice I/O Gateway (STT) → Orchestrator (Gemini, tool-call:
schedule_task) → Scheduler (nl_time_parser -> ScheduledTask row) → ack text
→ Voice I/O Gateway (TTS) → spoken confirmation to user
```

**B. Deep research flow ("research the latest trends in solid-state batteries
and email me a PDF")**
```
User request → Orchestrator (tool-call: run_deep_research)
  → Planner: 4 sub-questions
  → Researcher(s): web_search + academic_search per sub-question (parallel)
  → Verifier: drops any claim without >=2 independent corroborating sources
  → Writer: executive summary + key findings + actionable next steps
  → Document Generation: docx_builder + pdf_builder
  → Notification: emails/pushes the file, orchestrator also speaks a short
    actionable summary back to the user immediately (FR-6)
```

**C. Scheduled recurring research ("every Friday, research competitor
pricing and text me a summary")**
```
Scheduler (cron '0 9 * * 5') → run_due_task → re-enters Orchestrator exactly
as flow B → Document Generation → Notification (Twilio SMS with a link/short
summary, full report available in the web dashboard/Android app)
```

## 10. Recommended Final Repository Layout (Hybrid: Method A host + Method C brain)

This is the concrete layout to hand to a code-generation LLM as the first scaffold task, combining the fast-to-ship Method A backend with the Method C agentic research core (per the recommendation in 6.D), plus the client apps from Section 8.

```
lily-leo-x/
├── backend/                       # Method A: Django project (Section 6.A)
│   ├── apps/
│   │   ├── orchestrator/          # wraps the agent graph from research_engine/
│   │   ├── research_engine/       # Method C's graph.py/state.py/agents/tools
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── agents/
│   │   │   └── tools/
│   │   ├── voice/
│   │   ├── documents/
│   │   ├── scheduler/
│   │   ├── environment/
│   │   ├── memory/
│   │   └── notifications/
│   ├── config/
│   └── tests/
├── voice_gateway_bridge/          # standalone FastAPI service: Twilio Media
│   │                               # Streams <-> Gemini Live bridging (8.3)
│   └── main.py
├── android_app/                   # Section 8.2
├── web_dashboard/                 # React app, Section 8.4
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.voice_gateway
│   └── aws/ (Terraform or CDK for RDS/ElastiCache/ECR/App Runner/Secrets Manager)
├── .github/workflows/ci.yml
└── docs/
    └── LilyLeoX_Architecture_Plan.md   # (this document)
```

## 11. Implementation Roadmap (Phased)

| Phase | Scope | Exit criteria |
|---|---|---|
| 0 — Foundations | Repo scaffold, Django project, Gemini turn-based client, pytest harness, CI lint+test | `POST /v1/turn` returns a Gemini reply in an automated test |
| 1 — Core brain | tool_registry + router, scheduler models + Celery Beat, memory (Chroma) | Can schedule and correctly fire a one-off reminder end-to-end |
| 2 — Deep research | planner/researcher/verifier/writer agent graph, web+academic search, docx/pdf export | A fixed test topic produces a verified report with ≥90% citation-resolution in CI |
| 3 — Voice locally | STT (local Whisper) + Cartesia TTS + wake word, CLI/daemon voice loop | Can complete flow A and B (Section 9) fully by voice on a laptop |
| 4 — Cross-platform | Android app (turn-based first), web dashboard, FCM push reminders | Reminder created on phone fires as a push notification |
| 5 — Phone channel | Twilio number + Media Streams bridge + Gemini Live integration | Can call the assistant's number and complete flow A by phone |
| 6 — Hardening | Security review (7.8), cost guardrails, 30-day scheduler soak test, load test | All NFRs in Section 4 measured and met or documented as known gaps |
| 7 (optional) — Scale-out | Extract research-svc and scheduler-svc into Method B microservices on EKS | Same test suite green against the distributed deployment |

## 12. Risk Register & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| LLM/TTS API cost overrun | Budget blown, project unusable | Per-user token/request budget middleware (7.8), local Whisper/offline fallback mode |
| Hallucinated research claims presented as fact | Trust/safety failure | Mandatory verifier gate (7.3/7.8): unverified claims are labelled, never silently presented as fact |
| Voice cloning without consent | Ethical/legal exposure | Explicit consent record required before any `clone_voice_from_sample` call is allowed (7.1) |
| Real-time audio bridging complexity (Twilio↔Gemini Live) | Phase 5 slips | Ship the simpler turn-based Twilio `<Gather>`/`<Say>` fallback first (8.3, point 5); upgrade later |
| API/model names changing (Gemini Live model strings, Cartesia model snapshots move quickly) | Silent breakage | Pin exact model/version strings in config, not hard-coded in logic; add a startup health-check that verifies the configured model is still valid |
| Scheduler double-fire or missed jobs | User trust | Idempotent dispatch-id + audit log (7.5/7.8), soak-tested in Phase 6 |
| Scope creep across 3 architectures | Nothing ships | Follow the roadmap: build Method A + C fully first; Method B (Phase 7) is optional and explicitly deferred |

## 13. Appendix — Config Templates

```bash
# .env.example
GEMINI_API_KEY=
CARTESIA_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
DATABASE_URL=postgres://lily:lily@localhost:5432/lily_leo_x
REDIS_URL=redis://localhost:6379/0
CHROMA_PATH=./chroma_data
FCM_SERVER_KEY=
DJANGO_SECRET_KEY=
DAILY_TOKEN_BUDGET_PER_USER=200000
```

```text
# requirements.txt (Method A backend, core subset)
django>=5.0
djangorestframework
djangorestframework-simplejwt
channels
channels-redis
celery[redis]
django-celery-beat
google-genai
cartesia
langgraph
langchain-google-genai
chromadb
httpx
python-docx
weasyprint
dateparser
croniter
faster-whisper
watchdog
pytest
pytest-django
pytest-cov
freezegun
vcrpy
ruff
mypy
```

---

**End of document.** This plan is intentionally granular enough that each numbered subsystem (Section 7) or method (Section 6) can be given to a code-generation LLM as a standalone scaffolding task, in the phase order set out in Section 11.
