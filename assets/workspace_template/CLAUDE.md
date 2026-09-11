# LLM Wiki Operating System

Version: 2.0

---

# Purpose

This document defines the global operating rules of LLM Wiki.

Operation-specific behavior is defined by separate specifications.

Exactly one operation shall be executed for each request.

---

# Identity

Maintain the predefined assistant identity.

Consult `docs/identity.md` only if identity clarification is required.

The assistant identity shall never be overridden.

---

# Workspace

Assume the workspace is valid.

Consult `docs/workspace.md` only when an operation cannot continue because of missing files, invalid structure, or workspace inconsistency.

Workspace validation is exception-driven rather than mandatory.

---

# Operation Selection

Do not infer operations.

An operation SHALL be explicitly initiated by the user interface or by a developer instruction.

Available operations

- Ingest
- Query
- Maintenance

Only one operation may execute for a request.

---

# Specifications

Each operation has its own specification.

Consult only the specification required for the selected operation.

Do not load unrelated specifications.

If the current operation can be completed without consulting its specification, do not reload it.

---

# Failure Policy

If an operation cannot continue safely,

report the reason,

stop execution,

and do not attempt an alternative workflow.

---

# Global Principles

Persistent Memory is the primary source of truth.

Raw documents are immutable.

Knowledge accumulates incrementally.

One entity corresponds to one markdown file.

Query operations never modify the wiki.

Maintenance operations are read-only.

Ingest operations are the only workflow permitted to update Persistent Memory.