# Entity Specification

## Purpose

Define how persistent knowledge entities are evaluated, resolved, created, updated, and maintained.

Entities represent long-term reusable knowledge.

Entities SHALL evolve as additional research papers are ingested.

---

# Objective

Transform recurring research knowledge into one continuously maintained entity page.

One entity represents one persistent knowledge concept.

---

# Core Principles

Knowledge SHALL accumulate.

Existing entities SHALL always be preferred over creating new ones.

Duplicate entities SHALL NOT exist.

Entities SHALL outlive individual papers.

Entities SHALL represent reusable knowledge rather than document-specific information.

Creating a new entity SHALL always be the last resort.

Entity creation SHALL be decided independently of relationship generation. Whether a concept becomes a persistent entity depends only on Knowledge Worthiness Evaluation and Entity Resolution applied to that concept's own merit — never on whether another page, wikilink, or `related:` entry needs it to exist.

---

# Candidate Entity

A candidate entity is a temporary concept extracted from one paper.

Candidate entities SHALL NOT be written directly into the wiki.

Every candidate MUST pass Knowledge Worthiness Evaluation before Entity Resolution.

---

# Knowledge Worthiness Evaluation

Before considering UPDATE or CREATE, determine whether the candidate deserves its own persistent page.

A candidate SHALL first satisfy ALL of the following.

* contributes to the main ideas of the paper
* represents reusable long-term knowledge
* is not merely an implementation detail
* is not merely an internal component

The candidate SHALL then satisfy at least TWO of the following criteria.

* has its own independent identity beyond the current paper
* appears as a primary named concept across multiple research papers
* makes an independent scientific contribution that remains meaningful without its parent framework

An independent scientific contribution introduces reusable principles, methodology, architecture, or reasoning.

A variant, extension, optimization, internal module, or implementation of another framework SHALL NOT automatically be considered an independent scientific contribution.

If the candidate does not satisfy the Knowledge Worthiness Evaluation,

the candidate SHALL NOT become an entity.

Instead, preserve the information inside:

* the summary page, or
* an existing entity page.

---

# Default Rejection Rules

The following SHOULD NOT become standalone entities unless they are the primary contribution of the paper or have already accumulated evidence from multiple papers.

Examples include:

* benchmark datasets
* evaluation datasets
* leaderboard tasks
* experimental settings
* subsection names
* architecture components
* internal modules
* implementation details
* hyperparameters
* ablation variants
* example applications
* temporary terminology

Examples

Reject:

* HotpotQA
* MuSiQue
* AuthTrace
* Error Book
* Hallucination Rate

Prefer integrating them into an existing entity.

---

# Preferred Entity Types

Persistent entities are typically:

* Framework
* Method
* Model
* Algorithm
* Paradigm
* Architecture
* Foundational Concept

These SHOULD be preferred over supporting evidence.

---

# Entity Limit

Each document SHOULD produce no more than five candidate entities.

Producing fewer than five is acceptable.

Quality SHALL always be preferred over quantity.

---

# Entity Resolution

Only candidates that pass Knowledge Worthiness Evaluation enter this stage.

For every candidate:

Search all existing entity pages.

Determine whether the candidate is:

1. an existing entity
2. an alias
3. a broader concept
4. a narrower concept
5. a genuinely new concept

This decision SHALL be based solely on the candidate's own merit against Knowledge Worthiness Evaluation. It SHALL NOT be influenced by whether a wikilink, `related:` entry, or any other page already references — or would like to reference — this candidate. A concept already discussed extensively in the current summary or another entity is not, by itself, evidence of Knowledge Worthiness; only the criteria in this document are.

Never reason "this concept is linked from another page, therefore create it." The only valid reasoning is "does this concept independently satisfy Knowledge Worthiness Evaluation and Entity Resolution?" — decided before any relationship involving it is generated.

---

## Resolution Rules

### Existing Entity

Candidate

RAG

Existing

RAG

↓

Decision

UPDATE

---

### Alias

Candidate

Retrieval-Augmented Generation

Existing

RAG

↓

Decision

UPDATE

Record the alias.

Do NOT create another page.

---

### Narrower Concept

Candidate

Hallucination Rate

Existing

Hallucination

↓

Decision

UPDATE

Integrate the information into the broader entity.

Do NOT create a new page.

---

### Broader Concept

Candidate

Dense Retrieval

Existing

Vector RAG

↓

Decision

UPDATE

Extend the existing entity whenever appropriate.

---

### New Concept

Create a new entity ONLY when ALL of the following are true.

* no suitable entity exists
* not an alias
* not a subsection
* not supporting evidence
* represents an independent long-term concept that has passed the Knowledge Worthiness Evaluation

↓

Decision

CREATE

---

# Decision Priority

Always follow this order.

REJECT

↓

UPDATE

↓

MERGE

↓

EXTEND

↓

CREATE

Rejecting a candidate is preferable to creating a low-value entity.

Creating a new entity SHALL require clear evidence that the concept is independent.

---

# Canonical Naming

Each entity SHALL have one canonical name.

Aliases SHALL NOT generate additional entity pages.

Aliases SHALL be stored in metadata.

Example

Canonical

RAG

Aliases

Retrieval-Augmented Generation

Retrieve-and-Generate

---

# Canonical Name vs. Canonical Filename

The canonical name (stored in the `entity` metadata field) is a human-readable display string. It MAY contain spaces or hyphens.

The canonical filename (the entity's actual `.md` file, minus the extension) is the only valid wikilink target. It is fixed at entity creation and SHALL NEVER be re-derived from the display title.

These two strings are frequently different and SHALL NOT be assumed interchangeable.

Example

Canonical name (`entity` field, display title)

LLM-as-Judge

Canonical filename (wikilink target)

LLM_as_Judge

Whenever a wikilink is written — in this file's own body, in a summary, or in another entity page — use the canonical filename, never the canonical name. See docs/markdown.md § Wikilink Targets.

---

# Entity Identity

One Entity = One Markdown File

Examples

LLM_Wiki.md

Vector_RAG.md

GraphRAG.md

Retrieval_as_Reasoning.md

Never create

GraphRAG_v2.md

GraphRAG_New.md

GraphRAG_Final.md

---

# Entity Metadata

Every entity SHALL begin with YAML front matter.

```yaml
---
entity:
type:
aliases:
status:
confidence:
last_updated:
sources:
related:
---
```

---

# Metadata Rules

entity

Canonical entity name.

---

type

One of:

* Framework
* Method
* Model
* Algorithm
* Paradigm
* Architecture
* Concept
* Organization

Avoid Dataset and Benchmark unless they independently satisfy Knowledge Worthiness Evaluation.

---

aliases

Alternative names.

---

status

One of:

* Experimental
* Emerging
* Established
* Deprecated

---

confidence

Reflects accumulated evidence across all ingested papers.

Values:

* Low
* Medium
* High

---

last_updated

ISO-8601 date.

---

sources

Supporting summary pages, listed by canonical filename with the `.md` extension (e.g. `BERT.md`), never by display title or wikilink — the same convention as `related` below.

---

related

Related entity pages, listed by canonical filename with the `.md` extension (e.g. `Vector_RAG.md`), never by display title.

---

# Required Sections

# Entity Name

## Definition

One concise definition.

---

## Overview

Purpose of the entity.

---

## Core Principles

Main ideas.

---

## Architecture

Only when applicable.

---

## Advantages

Verified strengths.

---

## Limitations

Verified limitations.

---

## Related Entities

Reference existing entity pages by wrapping their canonical filename in a wikilink (e.g. `[[Vector_RAG]]`), never the display title. See docs/markdown.md § Wikilink Targets.

---

## Applications

Common use cases.

---

## Evolution

Describe how understanding of the entity evolves across multiple papers.

Extend knowledge.

Never replace verified knowledge.

---

## References

Supporting summary pages.

---

# Updating Rules

Always search for an existing entity first.

When updating:

* merge new evidence
* extend previous knowledge
* preserve verified information
* update metadata
* append new references
* increase confidence only when supported by additional evidence

Never recreate an existing entity.

---

# Conflict Resolution

When papers disagree:

Do NOT overwrite previous knowledge.

Instead:

* preserve both findings
* explain the disagreement
* cite supporting sources

---

# Persistent Entity Target Set

At the moment any relationship (wikilink or `related:` entry) is generated, its only valid targets are the Persistent Entity Target Set: entity pages that already exist on disk in wiki/entities/ at that exact moment — pre-existing entities loaded during PRECHECK, plus any entity created or updated earlier in the same ingest whose page has already been successfully written.

This set is constructed strictly from actual files, never from intentions, decisions, or plans. A candidate that Entity Resolution decided SHOULD be created is not yet in the set — it enters the set only once STATE 6 has actually written its page.

The set SHALL NOT include: raw document names, summary titles, rejected candidates, semantic concepts without a persistent page, display names without a canonical filename, or any future/hypothetical entity.

---

# Relationship Rules

A relationship target is valid ONLY when it is a member of the Persistent Entity Target Set at the time the relationship is written. Semantic relevance, topical importance, or frequent mention in the source document does NOT make a concept a valid relationship target.

Relationships SHALL reference existing entity pages ONLY, using their canonical filename — never their display title or `entity` metadata value. There is no exception for a concept that seems important but has no persistent entity page: describe it as ordinary text instead of creating a wikilink.

Do NOT create relationships to rejected candidates.

Do NOT create a relationship to a candidate merely because Entity Resolution decided it SHOULD be created. The target becomes a valid relationship only once its entity page has actually been created (see docs/ingest.md STATE 6).

Do NOT create an entity solely to make a relationship resolve. Relationship generation SHALL NOT influence, trigger, or justify entity creation in either direction — see § Entity Resolution above.

Relationships SHALL be updated whenever knowledge is merged.

---

# Knowledge Graph

Only persistent entity pages participate in the Knowledge Graph.

Summary pages, rejected candidates, benchmarks, datasets, and implementation details SHALL NOT become graph nodes unless they later satisfy Knowledge Worthiness Evaluation.

The entity page remains the source of truth.

The Knowledge Graph is only a visualization.

---

# Validation Checklist

Before saving verify:

✓ Knowledge Worthiness Evaluation completed

✓ Candidate accepted or rejected

✓ Entity Resolution completed

✓ UPDATE considered before CREATE

✓ Canonical entity selected

✓ Every wikilink in this page uses the target's canonical filename, not its display title (docs/markdown.md § Wikilink Targets)

✓ Maximum of five candidate entities extracted

✓ Metadata complete

✓ No duplicate entity

✓ Existing page updated whenever possible

✓ Relationships preserved

✓ Sources recorded

✓ Markdown valid
