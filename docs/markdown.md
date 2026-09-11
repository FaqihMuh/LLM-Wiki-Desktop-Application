# Markdown Specification

## Purpose

Define the standard markdown format used throughout the LLM Wiki.

All generated pages SHALL follow this specification.

Consistency has higher priority than formatting preference.

---

# General Rules

Markdown SHALL remain human-readable.

Markdown SHALL remain machine-readable.

Markdown SHALL be deterministic.

Markdown SHALL avoid unnecessary formatting.

---

# File Encoding

UTF-8

Unix line ending preferred.

---

# Heading Rules

Use ATX headings only.

Allowed:

# Title

## Section

### Subsection

Do NOT skip heading levels.

Example:

# Title

## Section

### Subsection

NOT

# Title

### Subsection

---

# Page Title

Every page SHALL contain exactly one H1 heading.

Example

# GraphRAG

---

# Paragraphs

Keep paragraphs concise.

Recommended length:

2–6 lines.

Avoid very long paragraphs.

---

# Lists

Use unordered lists whenever possible.

Example

- item
- item
- item

Ordered lists SHALL only be used for sequences.

---

# Tables

Markdown tables SHOULD be used only when the original source already contains structured tabular information.

Do NOT create decorative tables.

---

# Code Blocks

Use fenced code blocks.

Specify language whenever known.

Example

```python
print("Hello")
```

---

# Mathematical Expressions

Preserve mathematical notation whenever meaningful.

Use inline notation when short.

Example

$F(x)$

Use block notation for equations.

Example

$$
E = mc^2
$$

Do NOT rewrite mathematical meaning.

---

# Images

Do NOT embed images.

Describe important visual information using text.

---

# Hyperlinks

Prefer internal wiki links.

Example

[[GraphRAG]]

External URLs SHALL only appear when required.

---

# Wikilink Targets

A wikilink target SHALL be the exact filename of the target page, with the `.md` extension removed, and nothing else.

A wikilink target SHALL NOT be built from:

* the human-readable display title
* the `entity:` metadata value
* an alias
* any spaced or hyphenated form of the name

The display title and the wikilink target are two different strings that MAY diverge. Never assume they are interchangeable.

Example

Filename

LLM_as_Judge.md

Display title

LLM-as-Judge

Correct wikilink

[[LLM_as_Judge]]

Incorrect wikilink

[[LLM-as-Judge]]

---

Filename

Agent_Memory.md

Display title

Agent Memory

Correct wikilink

[[Agent_Memory]]

Incorrect wikilink

[[Agent Memory]]

---

Before writing any wikilink, confirm the target filename against wiki/index.md (or the entity file itself). Do NOT re-derive the target by guessing a transform of the display title.

This rule applies everywhere a wikilink is generated: summaries, entity pages, Related Entities sections, and any other prose section.

---

# Emphasis

Use bold only for important concepts.

Example

**Retrieval-Augmented Generation**

Avoid excessive emphasis.

---

# Quotes

Use blockquotes only when quoting original sources.

Example

> Original statement

---

# Horizontal Rules

Use

---

only for separating major sections.

---

# YAML Front Matter

Entity pages SHALL contain YAML metadata as defined in docs/entity.md.

Summary pages SHALL contain YAML metadata as defined in docs/summary.md.

Each page type SHALL follow its own specification.

Do NOT add metadata fields beyond those defined by the corresponding specification.

---

# Empty Sections

Do NOT generate empty headings.

Every heading SHALL contain meaningful content.

---

# Writing Style

Writing SHALL be:

- factual
- concise
- technical
- objective

Avoid:

- marketing language
- conversational tone
- unnecessary repetition
- unsupported claims

---

# Terminology

Preserve original technical terms whenever possible.

Avoid unnecessary translation of established AI terminology.

Example

Use:

Transformer

NOT

Transformator

---

# Knowledge Representation

Prefer structured knowledge over narrative.

Bad

"This paper is very interesting..."

Good

"The paper introduces a retrieval framework based on..."

---

# Consistency

The same concept SHALL always use the same name.

Example

Always use

GraphRAG

Never alternate between

Graph RAG

Graph-RAG

Graph Retrieval

unless referring to aliases.

---

# Validation Checklist

Before saving a page verify:

✓ One H1 title

✓ Correct heading hierarchy

✓ No empty sections

✓ Consistent terminology

✓ Human-readable

✓ Machine-readable

✓ No decorative formatting

✓ Markdown syntax valid