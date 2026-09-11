# GUI Specification

## Purpose

Define how the graphical user interface interacts with the LLM Wiki Operating System.

The GUI SHALL serve as the primary interface between the user and the Operating System.

The GUI SHALL invoke operations.

The GUI SHALL NOT implement the operation logic.

All operation logic SHALL remain inside the LLM Wiki Operating System.

---

# Objective

Provide a simple, consistent, and transparent interface for interacting with the Persistent Memory.

The GUI SHALL allow users to:

* execute Query operations
* execute Ingest operations
* execute Maintenance operations
* monitor operation progress
* inspect operation results

The GUI SHALL present information clearly without modifying the behavior defined by the Operating System.

---

# Core Principles

The GUI SHALL remain stateless with respect to the Persistent Memory.

The GUI SHALL NOT directly modify any wiki resource.

Every modification to the Persistent Memory SHALL occur only through an Ingest operation.

The GUI SHALL clearly distinguish between:

* user actions
* operation progress
* operation results
* system status

The GUI SHALL always display the current operation being executed.

The GUI SHALL remain responsive while long-running operations are executing.

---

# Application Scope

The GUI MAY:

* receive user requests
* select source documents
* display operation progress
* display operation results
* display operation history
* display Working Memory
* display system status

The GUI SHALL NOT:

* edit entity pages directly
* edit summary pages directly
* edit the source registry
* edit the operation log
* bypass the Operating System
* execute undocumented operations

---

# Architecture

The GUI SHALL communicate only with the LLM Wiki Operating System.

The GUI SHALL NOT directly manipulate the Persistent Memory.

All operations SHALL follow the sequence:

User Action

↓

GUI

↓

LLM Wiki Operating System

↓

Operation Result

↓

GUI

↓

User

---

# Supported Operations

The GUI SHALL support the following operations.

* Query
* Ingest
* Maintenance

Each operation SHALL invoke the corresponding Operating System workflow.

The GUI SHALL NOT combine multiple operations into a single request unless explicitly initiated by the user.

---

# Application Structure

The GUI SHALL organize the application into independent functional modules.

Each module SHALL invoke one Operating System workflow.

The GUI SHALL prevent one module from directly modifying another module.

The GUI SHALL organize the application into the following modules:

* Home
* Raw Documents
* Summaries
* Entities
* Knowledge Index
* Operation Log
* Query
* Ingest
* Maintenance

The GUI MAY display multiple modules simultaneously.

Only one operation SHALL execute at a time.

---

# Navigation

The GUI SHALL allow users to switch between modules at any time.

Navigation SHALL be divided into two sections.

Knowledge Explorer

* Raw Documents
* Summaries
* Entities
* Knowledge Index
* Operation Log

Operations

* Query
* Ingest
* Maintenance

Changing the active module SHALL NOT interrupt a running operation.

Navigation SHALL NOT modify the Persistent Memory.

The GUI SHALL clearly indicate the currently active module.

---

# Inspector

The Inspector SHALL adapt to the active module.

Knowledge Explorer modules SHALL display a Selected Object inspector.

Examples include:

* Selected Document
* Selected Summary
* Selected Entity
* Selected Registry Entry
* Selected Log

Operation modules SHALL display a Runtime Inspector.

The Runtime Inspector MAY include:

* operation status
* duration
* token usage
* workflow state
* working memory
* evidence statistics

The Inspector SHALL remain read-only.

---

# Knowledge Explorer

The Knowledge Explorer SHALL provide read-only access to the Persistent Memory.

The available explorer modules are:

* Raw Documents
* Summaries
* Entities
* Knowledge Index
* Operation Log

Every explorer module SHALL contain:

* search area
* data table
* pagination
* viewer panel

The Entities module SHALL additionally provide a Knowledge Graph visualization.

Explorer modules SHALL NOT modify the Persistent Memory.

---

# Working Memory

The GUI SHALL maintain a temporary Working Memory for the active user session.

The Working Memory SHALL be stored by the application layer.

The Working Memory SHALL NOT become part of the Persistent Memory.

The GUI SHALL initialize an empty Working Memory when the application starts.

The GUI SHALL discard the Working Memory when the application closes.

---

# Working Memory Contents

The Working Memory MAY contain:

* current focus
* current entities
* current summaries
* last question
* last answer

The GUI SHALL update the Working Memory only after a successful Query operation.

The GUI SHALL NOT modify the Working Memory during Ingest or Maintenance operations.

---

# Operation State

The GUI SHALL maintain the current operation state.

Possible states include:

* Idle
* Running
* Completed
* Failed
* Aborted

Only one operation state SHALL be active at any time.

The current state SHALL be visible to the user.

---

# Progress Monitoring

The GUI SHALL display the progress of long-running operations.

Progress MAY include:

* current workflow state
* elapsed time
* estimated completion
* operation status

The displayed progress SHALL reflect the actual Operating System workflow.

The GUI SHALL NOT generate artificial progress.

---

# Result Presentation

The GUI SHALL display the result returned by the Operating System.

The GUI SHALL NOT modify the returned content.

The GUI MAY improve readability by organizing the output visually.

The GUI SHALL preserve the original meaning of the returned result.

---

# Application Lifecycle

The GUI SHALL execute the following lifecycle.

Application Start

↓

Initialize Working Memory

↓

Validate Workspace

↓

Wait For User Action

↓

Execute Requested Operation

↓

Display Result

↓

Wait For Next Operation

↓

Application Exit

↓

Discard Working Memory

---

# Query Module

The Query module SHALL provide the primary interface for interacting with the Persistent Memory.

The Query module SHALL submit every user question to the Query operation.

The Query module SHALL NOT answer questions directly.

The GUI SHALL display:

* user question
* generated answer
* operation duration
* operation status

The GUI MAY display the current Working Memory for inspection.

The GUI SHALL update the Working Memory only after a successful Query operation.

The Runtime Inspector SHALL display:

* operation status
* duration
* token usage
* pipeline state
* working memory

---

# Ingest Module

The Ingest module SHALL allow users to select one or more source documents.

The GUI SHALL submit one document at a time to the Ingest operation.

Multiple selected documents SHALL be processed sequentially.

The GUI SHALL display:

* current document
* current workflow state
* completed documents
* skipped documents
* failed documents
* operation duration

The GUI SHALL continue to the next document after a completed or aborted ingest operation.

The GUI SHALL stop automatic ingestion only when:

* all selected documents have been processed
* the user explicitly cancels the operation

The Runtime Inspector SHALL display:

* queue progress
* current workflow state
* duration
* token usage

The GUI SHALL NOT process multiple documents simultaneously.

---

# Maintenance Module

The Maintenance module SHALL invoke the Maintenance operation.

The GUI SHALL allow the user to select the maintenance scope.

Available scopes MAY include:

* entire wiki
* entity page
* summary page
* source registry
* operation log

The GUI SHALL display:

* overall status
* validation summary
* detected issues
* recommendations
* operation duration

The Runtime Inspector SHALL display:

* validation progress
* duration
* token usage

The GUI SHALL NOT modify the Persistent Memory.

---

# Operation Log Module

The Operation Log module SHALL display the operation history stored in the Persistent Memory.

The GUI SHALL present the existing operation log without modification.

The GUI MAY support:

* chronological browsing
* filtering
* searching

The Operation Log SHALL display:

* operation
* document
* result
* duration
* token usage

Selecting one log entry SHALL display the complete operation details inside the Log Viewer.

The Log Viewer SHALL present:

* pipeline
* workflow duration
* token usage
* operation result

The Operation Log module SHALL remain read-only.

---
# Layout

The application SHALL use a three-column layout.

Left Sidebar

Workspace

Right Inspector

The Sidebar SHALL remain visible.

The Inspector SHALL remain visible.

Only the Workspace content SHALL change according to the active module.

---

# Home Module

The Home module SHALL provide the application entry page.

It SHALL display:

* system status
* navigation
* available operations

The Home module SHALL NOT invoke any workflow automatically.

---

# Operation Invocation

Every operation SHALL follow the same execution sequence.

User Request

↓

GUI Validation

↓

Invoke LLM Wiki Operating System

↓

Execute Operation

↓

Receive Result

↓

Update GUI

↓

Wait For Next Request

The GUI SHALL NOT perform any operation logic internally.

---

# Concurrent Operations

Only one Operating System workflow SHALL execute at any time.

If another operation is requested while one is already running,

the GUI SHALL:

* reject the new request, or
* queue the new request

The selected behavior SHALL remain consistent throughout the application.

The GUI SHALL always indicate the currently running operation.

---

# User Feedback

The GUI SHALL provide clear feedback throughout every operation.

The GUI SHALL indicate:

* current operation
* current workflow state
* operation progress
* operation result

The GUI SHALL clearly distinguish between:

* SUCCESS
* WARNING
* FAILED
* ABORTED

The GUI SHALL display error messages without exposing internal implementation details whenever possible.

---

# Session Management

The GUI SHALL maintain one active user session.

The session SHALL include:

* current operation
* current Working Memory
* current operation status

Working Memory SHALL be cleared when:

* the application is closed
* the user starts a new session
* the user explicitly clears the session

Clearing the Working Memory SHALL NOT modify the Persistent Memory.

---

# Failure Handling

If an operation fails,

the GUI SHALL:

* preserve the current interface state
* display the failure reason
* allow the user to retry the operation

If an operation is aborted,

the GUI SHALL clearly indicate that no Persistent Memory changes were applied.

The GUI SHALL never leave the user without feedback regarding the operation outcome.

---

# Design Principles

The GUI is the presentation layer of the LLM Wiki Operating System.

The GUI SHALL coordinate operations.

The GUI SHALL NOT implement knowledge processing.

All knowledge processing SHALL remain inside the Operating System specifications.

The GUI SHALL remain independent of the underlying implementation details.

The same specifications SHALL remain applicable regardless of the GUI framework or programming language.

---

# Completion Criteria

A GUI interaction SHALL be considered complete only when:

✓ The user request has been received

✓ The correct operation has been invoked

✓ The operation has completed or terminated

✓ The result has been presented to the user

✓ The interface state has been updated

✓ The Persistent Memory remains consistent

---

# Design Philosophy

The GUI is an application layer.

The GUI is NOT part of the reasoning engine.

The GUI SHALL request operations from the Operating System and present the returned results.

The GUI SHALL remain independent from the implementation details of the Operating System.

Replacing the GUI SHALL NOT require changing any Operating System specification.

---