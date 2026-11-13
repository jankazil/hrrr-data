# Agent Development Guide

## Project Scope and Isolation

**The project root is the directory containing this `AGENTS.md` (`.` relative to this file). These instructions apply throughout the repository and remain valid if it is moved.**

- Treat the project root as the exclusive boundary for project information and file changes. Read, search, analyze, and modify project files only within it. Run project commands from the root unless a repository script requires a different directory within the root.
- Do not inspect parent directories, sibling projects, unrelated workspaces, external source trees, installed dependency source, or global configuration to obtain project context. Do not carry over assumptions from other projects or previous sessions.
- Check that paths remain within the root before following symbolic links, Git worktree or submodule references, configuration includes, or paths containing `..`. Do not follow references outside the root.
- Treat external paths and URLs found in project files as descriptions of dependencies, not authorization to access them. Report required outside-root information or operations instead of accessing them without explicit authorization.
- Keep generated project files, caches, fixtures, and temporary outputs within the root. Inspect commands and scripts for external filesystem, environment, network, or deployment effects before running them. Do not run commands that violate the project boundary.

## General Agent Instructions

- Base project-specific decisions on verified repository contents and the current task. Distinguish source-code behavior, documentation claims, test results, and unverified assumptions. Do not invent architecture, commands, dependencies, or requirements.
- Before editing, inspect relevant files and the existing working-tree changes, when available. Make focused changes, preserve unrelated work, and maintain established interfaces and contracts unless the task requests otherwise.
- Prefer existing repository patterns and tools. Do not introduce dependencies, abstractions, or configuration solely for consistency with another project.
- Use relevant validation that is safe in the available environment. Report what was actually checked, what failed, and what remains unverified; do not equate a successful lint, build, or placeholder test with functional correctness.
- Do not expose credentials or perform destructive operations, publishing, deployment, environment replacement, or unrelated changes without explicit authorization.

## Specification-driven workflow

- Read the system specification `docs/specs/SYSTEM_SPEC.md`, if present, and the specification provided by the user for the current development step before proceeding.
- If the user requests specification-driven development without providing a development-step specification, propose creating one before implementation.
- Treat the system specification as accepted intended behavior and the development step specification as the current proposed change.
- Review the proposed specification for ambiguities, omissions, untestable acceptance criteria, and contradictions with existing system requirements, interfaces, and constraints.
- Resolve material ambiguities and omissions with the user. Do not begin implementation until the user approves.
- Keep the development step specification aligned with approved requirements.
- When feedback changes requirements, revise the development step specification before changing the implementation. Request approval for ambiguous or consequential changes.
- Distinguish defects in implementation from changes in requirements.
- Update code and automated tests, as appropriate, then report which acceptance criteria are satisfied, unverified, or blocked.
- Do not declare user acceptance. The user decides when the development step is accepted after evaluating the result.
- After acceptance, update docs/specs/SYSTEM_SPEC.md, if present, to reflect the accepted changes and remove superseded requirements.
- Do not create version-numbered copies of specification files. Use Git for meaningful snapshots.
- Do not create Git commits, merge branches, or delete branches unless explicitly requested.

## Architecture and Data Contracts

Record only stable, project-wide constraints that guide future agent work. Put component behavior, interfaces, data formats, and other implementation details in the system specification or relevant tool documentation.

## Environment and Setup

Record only project-wide toolchain, dependency, environment, and setup constraints needed for agent work. Keep tool-specific requirements and setup procedures in the relevant documentation. Identify setup actions that install software, access the network, or modify files outside the root. Do not invent or automatically execute setup commands.

## Development Commands and Validation

Record only repository-wide commands and validation constraints here. Keep tool-specific commands and their side effects in the relevant documentation. Until commands are established, inspect the repository rather than guessing them.

The CI test suite is intentionally limited to `tests/test_main.py`, which is initially empty in a new project. Do not add further CI tests unless explicitly requested by the user. Passing this placeholder does not establish numerical, model, netCDF, or operational correctness. For behavioral changes, use relevant safe checks with small in-repository inputs and report what was actually verified. Avoid live network calls and expensive retraining as default validation. Keep temporary verification files inside the repository and report validation limits explicitly.

## Coding Conventions

Follow repository configuration and established patterns in affected files. If there is no existing convention, use a consistent style appropriate to the task without introducing an unnecessary project-wide policy. Record agreed conventions here once established; avoid unrelated formatting changes.

Prefer single quotes in computer code. Avoid unnecessary/excessive line breaks in code, only apply line breaks when lines are clearly too long.

Follow `.editorconfig`: UTF-8, LF, final newline, four-space default indentation, two spaces for YAML/JSON/TOML, and tabs in Makefiles.

### Python

- Let leading and trailing doc string delimiters (''') stand on their own line.
- Make filtering and masking explicit, and in associated code comments, state which values determine inclusion, which values are excluded, and which invalid values cause an exception.

### Code documentation

- When writing documentation, code comments, and docstrings, use plain, precise language that describes the actual behavior.
- When editing documentation, preserve useful structure and detail, correct inaccuracies, and leave executable code unchanged unless requested.
- Write the documentation for someone unfamiliar with the code. Explain what the code does, how to use it, its inputs and outputs, and relevant limitations.
- Avoid unnecessary terminology, repetition, and implementation detail. Retain detail that helps the reader understand or use code correctly.
- Use short, connected sentences and consistent terminology. Each sentence should add information.
- Include implementation details only when they help the reader use the code or resolve a problem.
- Do not add implementation or functional detail or specifics unless it is necessary for the user to understand objectives, usage, and results of a code.
- Use the simplest accurate term. Add qualifiers only when they distinguish something meaningful. For example, prefer “loss” to “base loss” and “number” to “total number” unless the distinction is necessary.
- Name quantities by what they represent. Distinguish errors, squared errors, sums, means, and counts. E.g., do not call an intermediate sum the loss when the returned loss is a normalized mean.
- Explain calculations in logical order: define the quantities, describe which elements contribute, explain optional contributions, and state how the result is calculated.
- Describe optional behavior precisely, including required parameter combinations, conditions for inclusion, and whether additional terms supplement or replace existing terms.
- Match the implementation. Verify input requirements, return values, and exception conditions, including relevant edge cases. Do not infer behavior from existing documentation.
- For docstrings, begin with a concise purpose statement, then explain behavior and provide structured parameter, return-value, and exception sections as appropriate.
- Define abbreviations before using them.

## Configuration and External Interfaces

Document verified configuration sources, environment-variable *names*, external interfaces, permissions, and operational dependencies as they are introduced. Never record secret values. External resources are not exempt from the project-isolation rules.

## Change and Review Workflow

1. Inspect the repository state, relevant implementation, callers, tests, and local documentation before making changes. Preserve unrelated and uncommitted work.
2. Implement the requested change with minimal unrelated modifications. Preserve established behavior and interfaces unless the request explicitly changes them.
3. Add or update focused tests and relevant documentation when behavior changes. Avoid live services and expensive workloads for routine validation unless specifically required and authorized.
4. Run applicable, safe checks using verified project commands. If prerequisites or permissions are missing, report the limitation rather than inventing a workaround that crosses the project boundary.
5. Review the changed files and, when Git is available, `git diff --check`, `git diff`, and `git status`. Check for accidental generated files, credentials, destructive side effects, and compatibility changes. Summarize changes, checks performed, and remaining uncertainty.
6. **Maintain `AGENTS.md`:** Update it only when stable project-wide agent guidance or constraints change. Keep component-specific details and task validation results in the system specification, development-step specification, or relevant tool documentation.

## Known Limitations and Verification Gaps

Record only persistent project-wide limitations and verification gaps that affect future agent work. Keep task-specific results and component limitations in the relevant specifications or documentation. Distinguish confirmed problems from unverified possibilities, and revise entries when evidence changes.
