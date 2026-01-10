# Hands-on Skills

A collection of hands-on skills for students to explore and practice when learning the Skills concept in Claude Code. These examples accompany **Lesson 04 of Chapter 5** in the AI Native Development book.

**Reading Material:** [Claude Code Features and Workflows](https://ai-native.panaversity.org/docs/AI-Tool-Landscape/claude-code-features-and-workflows)

## Skills

| Skill | Purpose |
|-------|---------|
| **browsing-with-playwright** | Browser automation using Playwright MCP. Navigate websites, fill forms, click elements, take screenshots, and extract data. Use when tasks require web browsing, form submission, web scraping, UI testing, or any browser interaction |
| **fetch-library-docs** | Token-efficient library documentation fetcher for various programming languages, providing code examples, API references, and best practices. |
| **doc-coauthoring** | Guide users through a structured workflow for co-authoring documentation including proposals, technical specs, decision docs, and similar structured content |
| **docx** | Comprehensive Word document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction |
| **internal-comms** | Resources to help write internal communications including 3P updates, company newsletters, FAQs, status reports, leadership updates, and incident reports |
| **pdf** | PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms |
| **pptx** | PowerPoint presentation creation, editing, and analysis including layouts, speaker notes, comments, and visual design |
| **interview** | Conducts discovery conversations to understand user intent and agree on approach before taking action. Prevents building the wrong thing by uncovering WHY behind WHAT through structured questioning |
| **skill-creator** | Guide for creating effective skills that extend Claude's capabilities with specialized knowledge, workflows, or tool integrations |
| **skill-creator-pro** | Creates production-grade, reusable skills with embedded domain expertise. Guides creation of new skills, improves existing ones, and provides patterns for 5 skill types (Builder, Guide, Automation, Analyzer, Validator) |
| **skill-validator** | Validate any skill against production-level quality criteria. 7 weighted criteria, 0-100 scoring, actionable feedback with prioritized recommendations |
| **theme-factory** | Toolkit for styling artifacts (slides, docs, reports, HTML) with 10 pre-set professional themes or custom on-the-fly theme generation |
| **xlsx** | Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization |

## Rice Export FSMS Skills

Custom skills for ISO 22001:2018 Food Safety Management System compliance in rice mill operations.

| Skill | Purpose |
|-------|---------|
| **sqlmodel-architect** | SQLModel database architecture for Rice Export FSMS with ISO 22001:2018 compliance. Creates Document and Task models with Neon Postgres connection |
| **fastapi-route-wizard** | FastAPI route generation with async endpoints, Pydantic validation, and OpenAPI docs for the food safety management system |
| **pytest-inspector** | Pytest test generation with async support, fixtures, and coverage for SQLModel models and FastAPI endpoints |
| **iso-gap-analyzer** | ISO 22001:2018 gap analysis for FSMS documents. Classifies documents, audits against ISO clauses, checks rice mill hazards |
| **doc-controller** | Document gatekeeper implementing ISO 22001:2018 Clause 7.5.3. Manages document state transitions, version control, and Master Document Register |
| **fsms-task-extractor** | Extracts operational tasks from controlled documents by parsing "shall" statements and converting to database tasks with ISO clause mapping |

**User Guide:** See [USER_GUIDE.md](./USER_GUIDE.md) for complete usage instructions.
