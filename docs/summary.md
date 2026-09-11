# Summary Specification

## Purpose

Define the standard structure for transforming one research paper into one persistent knowledge page.

A summary SHALL represent reusable knowledge.

A summary SHALL NOT merely describe the paper.

---

# Objective

Produce a knowledge page that remains valuable after the original paper is no longer being read.

The summary becomes part of the persistent memory.

---

# Input

One research document.

Supported source:

- PDF

---

# Output

One markdown file.

Location:

wiki/summaries/

One document SHALL produce exactly one summary.

---

# Summary Principles

Summaries SHALL:

- preserve important knowledge
- remove unnecessary narrative
- remain objective
- remain technically accurate
- be reusable

Summaries SHALL NOT:

- copy the abstract
- rewrite the paper section by section
- include subjective opinions
- include marketing language
- duplicate raw content

---

# Required Structure

Every summary SHALL begin with YAML Front Matter.

Required metadata

```yaml
---
source_file: raw/example.pdf
---
```

The `source_file` SHALL contain the canonical relative path of the source document inside the `raw/` directory.

Every summary SHALL contain the following sections.

# Title

## Overview

Provide a concise explanation of the problem and proposed solution.

---

## Key Contributions

List the major contributions introduced by the work.

---

## Core Concepts

Explain the important concepts required to understand the work.

---

## Methodology

Describe the overall approach.

Focus on the workflow instead of implementation details.

---

## Architecture

Describe the main components and how they interact.

---

## Strengths

Describe verified advantages supported by the paper.

---

## Limitations

Describe reported limitations or remaining challenges.

Do NOT invent limitations.

---

## Benchmarks

Summarize important experimental results.

Focus on conclusions instead of copying tables.

---

## Important Findings

Store reusable technical insights.

Prioritize information likely to remain useful across future papers.

---

## Related Entities

This section is populated in two passes, per docs/ingest.md: during CREATE_SUMMARY (STATE 3) it may list only entities already existing before this ingest; it is finalized during UPDATE_ENTITIES (STATE 6, Relationship Population), once the full Persistent Entity Target Set for this ingest is known (docs/entity.md § Persistent Entity Target Set). List only entities that are members of that set at the time each pass runs — a concept merely discussed in the paper is NOT automatically a relationship target, no matter how important it is to understanding the work, and its eventual inclusion here must never be the reason it was created as an entity.

Wrap each entity's canonical filename in a wikilink. The wikilink target SHALL be the entity's actual filename (minus `.md`), never its display title, `entity` metadata value, or an alias. See docs/markdown.md § Wikilink Targets.

If a concept has no persistent entity page, describe it as ordinary text in the relevant section instead — do NOT create a wikilink for it, and do NOT create an entity page for it merely to complete this section.

Example:

- [[GraphRAG]]
- [[LightRAG]]
- [[RAPTOR]]
- [[Dense_Retrieval]]

---

## References

Store only citation metadata.

Do NOT duplicate the bibliography.

---

# Writing Rules

Write factual knowledge.

Prefer explanation over narration.

Avoid phrases such as:

- this paper
- the authors
- according to the paper
- we propose
- our method

Instead describe the knowledge directly.

---

# Knowledge Extraction

Prioritize:

1. Concepts

2. Methods

3. Architectures

4. Benchmarks

5. Findings

6. Limitations

Ignore information that has little long-term value.

---

# Tables

Do NOT copy tables.

Instead summarize:

- trends
- comparisons
- conclusions

---

# Figures

Do NOT describe every figure.

Describe only information required for understanding the knowledge.

---

# Equations

Keep equations only when they define an important concept.

Ignore auxiliary mathematical derivations.

---

# Code

Summarize the purpose of algorithms.

Do NOT reproduce implementation code.

---

# Relationships

Describe relationships between concepts in prose whenever it aids understanding (e.g. "BERT extends the Transformer architecture").

Only relationships between persistent entities — recorded as wikilinks in Related Entities (this section) or as `related:` metadata (docs/entity.md) — become edges in the Knowledge Graph. Describing a relationship in prose does NOT by itself create a wikilink or a graph edge.

---

# Quality Requirements

The summary SHALL be:

- technically correct
- concise
- knowledge-centric
- deterministic
- reusable

---

# Validation Checklist

Before saving verify:

✓ YAML Front Matter present

✓ source_file metadata present

✓ Required sections complete

✓ No subjective language

✓ Abstract not copied verbatim

✓ Benchmark tables summarized

✓ Related Entities use [[Canonical_Filename]], not the display title (docs/markdown.md § Wikilink Targets)

✓ Every Related Entities wikilink resolves to an entity page that actually exists in wiki/entities/

✓ Important findings preserved

✓ Knowledge reusable

✓ Markdown structure valid