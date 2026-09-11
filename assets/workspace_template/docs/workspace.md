# Workspace

## Purpose

Define the working directory, file structure, and ownership of every resource used by LLM Wiki.

The workspace SHALL remain organized, deterministic, and reproducible.

---

# Root Directory

The project root is the only valid working directory.

The system SHALL NOT intentionally access files outside the project root unless explicitly required by the user.

---

# Workspace Structure

raw/
wiki/
benchmark/
gui/
docs/
CLAUDE.md

---

# Raw Sources

Directory:

raw/

Purpose:

Store immutable source documents.

Rules:

- PDF files SHALL be stored here.
- Raw files SHALL NEVER be modified.
- Raw files SHALL NEVER be renamed automatically.
- Raw files SHALL remain the source of truth.
- Derived knowledge SHALL NEVER replace raw sources.

---

# Wiki

Directory:

wiki/

Purpose:

Persistent memory maintained by the system.

Contents:

summaries/
entities/
index.md
log.md

Rules:

The system MAY create new files inside the wiki.

The system MAY update existing wiki pages.

The system SHALL preserve knowledge continuity.

The wiki is the only persistent memory maintained by the system.

---

# Summaries

Directory:

wiki/summaries/

Purpose:

Store one summary page for each ingested document.

Rules:

One source document SHALL produce one summary.

Summary filenames SHALL remain stable.

---

# Entities

Directory:

wiki/entities/

Purpose:

Store entity pages representing concepts, methods, datasets, models, benchmarks, organizations, and other important knowledge.

Rules:

Existing pages SHALL be updated before creating new ones.

Duplicate entities SHALL be merged.

---

# Index

File:

wiki/index.md

Purpose:

Provide a structured overview of the knowledge base.

Rules:

The index SHALL always reflect the current wiki.

The index SHALL be updated after every successful ingest.

---

# Log

File:

wiki/log.md

Purpose:

Maintain a chronological history of system activities.

Rules:

Every ingest SHALL append one log entry.

Existing log entries SHALL NEVER be modified.

---

# Documentation

Directory:

docs/

Purpose:

Store operational specifications.

Rules:

These documents define system behavior.

The system SHALL NOT modify specification documents unless explicitly requested by the developer.

---

# GUI

Directory:

gui/

Purpose:

Provide the user interface and initiate system operations.

Rules:

The GUI SHALL NOT contain persistent knowledge.

The GUI SHALL NOT implement business logic.

The GUI SHALL invoke operations but SHALL NOT replace system specifications.

---

# Benchmark

Directory:

benchmark/

Purpose:

Store evaluation datasets and benchmark results.

Rules:

Benchmark data SHALL remain independent from the persistent memory.

Benchmark operations SHALL NEVER modify wiki contents.

---

# File Ownership

raw/

Owner:
User

---

wiki/

Owner:
LLM Wiki

---

docs/

Owner:
Developer

---

gui/

Owner:
Developer

---

benchmark/

Owner:
Developer

---

# Workspace Constraints

The system SHALL NOT create random folders.

The system SHALL NOT duplicate files.

The system SHALL NOT rename stable resources without explicit instruction.

The system SHALL keep the workspace deterministic.

---

# Validation Checklist

Before modifying files verify:

✓ Correct directory

✓ Correct ownership

✓ Correct operation

✓ No raw source modified

✓ Wiki consistency preserved

✓ Documentation unchanged