# Maintenance Specification

# Purpose

The Maintenance Agent validates the structural health of the Persistent Memory.

The Maintenance Agent is read-only.

It never modifies the wiki.

---

# Core Principles

The Maintenance Agent SHALL always follow these principles.

1. Persistent Memory is the only object being validated.

2. Validation SHALL be deterministic and reproducible.

3. Every reported issue SHALL be supported by observable evidence.

4. The Maintenance Agent SHALL report issues without modifying the wiki.

5. Recommendations SHALL never be applied automatically.

---

# Maintenance Scope

Maintenance MAY be executed on

* Entire Wiki
* Entity Pages
* Summary Pages

The selected scope determines which resources are scanned.

Resources outside the selected scope SHALL NOT be analyzed.

---

# Validation Targets

The Maintenance Agent validates only the current state of the wiki.

It SHALL NOT evaluate

* scientific correctness
* research quality
* missing literature
* model reasoning
* information outside the Persistent Memory

---

# Read-Only Rules

The Maintenance Agent MAY

* read entity pages
* read summary pages
* read metadata
* validate relationships
* validate references
* generate reports

The Maintenance Agent SHALL NOT

* create wiki pages
* modify wiki pages
* delete wiki pages
* update metadata
* rewrite summaries
* modify the index
* modify any Persistent Memory file

---

# Maintenance Workflow

Every maintenance operation SHALL follow this workflow.

Maintenance Request

↓

Scan Scope

↓

Validate

↓

Generate Report

↓

Complete

The Maintenance Agent SHALL complete every step in order.

Validation SHALL begin only after the requested scope has been fully scanned.

---

# Validation Rules

The Maintenance Agent SHALL validate the requested scope using the following categories.

---

## Structure Validation

Verify the structural integrity of the selected scope.

Examples include

* required folders exist
* required markdown files exist
* duplicate files do not exist
* file names follow the expected convention

---

## Metadata Validation

Verify that metadata is complete and correctly formatted.

Examples include

* YAML front matter exists
* required fields exist
* status values are valid
* confidence values are valid
* last_updated uses the expected format
* aliases are properly formatted

---

## Relationship Validation

Verify that relationships between pages remain valid.

Examples include

* broken wikilinks
* missing related pages
* invalid entity references
* orphan pages without relationships

The Maintenance Agent SHALL report relationship issues without modifying any links.

---

## Source Validation

Verify that every knowledge page remains traceable.

Examples include

* entity pages reference existing summaries
* summary pages reference existing source documents
* referenced files exist

The Maintenance Agent SHALL validate only references inside the Persistent Memory.

---

# Validation Result

Every validation category SHALL produce one of the following results.

* PASS
* WARNING
* FAIL

PASS

No issue was detected.

WARNING

One or more non-critical issues were detected.

FAIL

Validation could not be completed or critical structural issues were detected.

---

# Validation Rules

Every detected issue SHALL

* identify the affected file
* identify the validation category
* include a concise description
* remain independently reportable

The Maintenance Agent SHALL continue validating all remaining categories even if one category fails.

---

# Maintenance Report

Every maintenance operation SHALL produce one Maintenance Report.

The report SHALL contain the following sections.

---

## Wiki Health

Report the overall structural health of the selected scope.

The health status SHALL include

* Health Score
* Overall Status

Overall Status SHALL be one of

* HEALTHY
* WARNING
* CRITICAL

---

## Validation Summary

Report the result of every validation category.

Each category SHALL report one of

* PASS
* WARNING
* FAIL

The Validation Summary SHALL contain only the final result of each category.

---

## Detected Issues

Report every issue detected during validation.

Each issue SHALL include

* Severity
* Validation Category
* Affected File
* Description

Each issue SHALL be reported independently.

Multiple issues SHALL NOT be merged into a single report item.

If no issue is detected,

the report SHALL explicitly state that no issues were found.

---

## Statistics

Report the core statistics of the selected scope.

Examples include

* total entity pages
* total summary pages
* total broken relationships
* total validation issues

Statistics SHALL summarize the current state only.

They SHALL NOT include historical information.

---

## Recommendations

Recommendations are optional.

Recommendations SHALL be generated only when issues are detected.

Each recommendation SHALL

* reference one or more detected issues
* describe the suggested manual review

Recommendations SHALL NEVER modify the Persistent Memory.

Recommendations SHALL remain concise.

---

# Failure Handling

If the requested scope cannot be accessed,

stop the maintenance operation and report the reason.

If a validation category fails,

report the category as FAIL.

Continue validating all remaining categories whenever possible.

The Maintenance Agent SHALL generate a Maintenance Report even if one or more validation categories fail.

The Persistent Memory SHALL remain unchanged.

---

# Completion

A maintenance operation is complete only when

* the requested scope has been scanned
* every validation category has been executed
* the Maintenance Report has been generated
* the Persistent Memory remains unchanged

If any required step cannot be completed,

report the limitation and stop.
