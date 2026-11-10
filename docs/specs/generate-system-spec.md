# Task: Generate or Update the System Specification

Analyze the current repository and generate or update `docs/specs/SYSTEM_SPEC.md`, following the instructions in `AGENTS.md`.

The document serves as the system specification for subsequent specification-driven development (SDD). It must be understandable to both human readers and AI coding agents.

If `SYSTEM_SPEC.md` already exists, review and update it rather than automatically replacing it. Preserve accurate and relevant content, correct inaccuracies, and incorporate verified changes in system behavior.

## 1. Repository Inspection Procedure

Inspect the repository systematically before drafting or updating the specification.

### Step 1: Establish Repository Structure

- Identify the project root and inspect the Git working-tree status.
- Inventory tracked source files, configuration, tests, documentation, and relevant project resources.
- Identify the principal directories and their responsibilities.
- Exclude generated files, caches, virtual environments, and large data files from exhaustive inspection unless their contents are necessary.
- Do not modify repository contents during inspection.

### Step 2: Examine Existing Documentation and Configuration

- Read `AGENTS.md`, `README.md`, `SYSTEM_SPEC.md` (if present), and other relevant project documentation.
- Examine dependency declarations, configuration files, and available execution instructions.
- Identify documented functionality, intended workflows, and known limitations.
- Treat documentation as evidence of intended behavior, not necessarily of implemented behavior.
- If `SYSTEM_SPEC.md` exists, identify its established requirements and compare them with the current implementation. Do not silently replace accepted requirements with divergent implementation behavior.

### Step 3: Identify Entry Points and User Workflows

- Identify scripts, command-line interfaces, application entry points, and other mechanisms through which users interact with the system.
- Trace the principal execution paths from user inputs and configuration through processing to observable outputs.
- Identify available operations, user-selectable options, and their effects.
- Determine how the principal components cooperate to provide the system's functionality.

### Step 4: Analyze Implementation and Data Flows

- Inspect the relevant source files, functions, classes, and their relationships.
- Identify significant algorithms, processing steps, data transformations, and control flows.
- Examine configuration handling, input validation, error handling, and output generation.
- Document important data formats, interfaces, dependencies, and constraints.
- Prioritize understanding observable system behavior over exhaustively documenting implementation details.

### Step 5: Examine Tests and Verify Findings

- Inspect existing tests to identify expected behavior, supported use cases, and edge cases.
- Compare documentation claims with the implementation and tests.
- Run relevant validation commands only when their behavior and side effects are understood and they comply with `AGENTS.md`.
- Do not execute expensive computations, external services, or workflows with potentially destructive effects without authorization.
- Distinguish behavior verified by execution from behavior inferred through source inspection.

### Step 6: Reconcile Findings

- Cross-check findings across source code, configuration, documentation, and tests.
- Identify discrepancies, uncertainties, and undocumented functionality.
- Reinspect relevant files where necessary to resolve inconsistencies.
- Establish the principal functionality and architecture before drafting the specification.
- Record unresolved questions rather than making unsupported assumptions.
- If updating an existing specification, identify additions, modifications, and removals justified by verified evidence. Flag discrepancies between accepted requirements and implementation for user resolution.

## 2. Generate or Update `SYSTEM_SPEC.md`

Organize the document into the following sections, adapting the structure where appropriate.

### System Overview
Explain the system's purpose, primary functions, and intended use. Write this section from the user's perspective, without requiring familiarity with the implementation.

### User-Facing Functionality
Describe the capabilities available to users, how they are accessed, their inputs, and their observable results. Explain important workflows and options.

### Functional Specifications
Document the system's behavior, including relevant processing rules, data transformations, and relationships between functions. Distinguish accepted requirements from observed implementation behavior where they differ.

### Architecture and Components
Describe the principal software components, their responsibilities, and interactions. Explain the overall data flow without unnecessarily documenting implementation details.

### Data and Interfaces
Describe important input and output formats, data structures, configuration options, external interfaces, and compatibility requirements.

### Operational Requirements and Constraints
Document established dependencies, execution requirements, limitations, and relevant performance constraints.

### Known Limitations and Unresolved Questions
Identify significant uncertainties, undocumented behavior, inconsistencies, and functionality that could not be verified.

## 3. Documentation Requirements

- Use clear, precise Markdown understandable to a technically competent reader unfamiliar with the repository.
- Prioritize a coherent explanation of the system over an exhaustive inventory of functions, classes, or files.
- Explain functionality from the user's perspective before describing its implementation.
- Provide references to relevant source files for important technical specifications.
- Document only behavior supported by repository evidence or established requirements. Clearly identify unverified claims.
- Distinguish current behavior from proposed or intended functionality.
- Avoid redundant information, speculative details, and unnecessary implementation specifics.
- Preserve accurate existing documentation when updating the specification.
- Make the document suitable for maintenance as the system evolves.

## 4. Acceptance Criteria

The generated or updated `SYSTEM_SPEC.md` must satisfy the following criteria:

- **Functional coverage:** Describe all principal user-facing capabilities identified during repository inspection.
- **Behavioral specificity:** Explain the relevant inputs, operations, and observable outputs with sufficient precision to support subsequent development.
- **Architectural coverage:** Describe the principal components, their responsibilities, and significant data flows.
- **Traceability:** Support important technical claims with references to repository source files, configuration, tests, or established documentation.
- **Consistency:** Identify discrepancies between documentation, accepted requirements, implementation, and tests. Do not silently reconcile contradictions.
- **Completeness:** Address all applicable document sections and explicitly identify significant unresolved questions or verification gaps.
- **Readability:** Provide a coherent, logically organized description understandable without examining the source code.
- **Maintainability:** Avoid unnecessary implementation details and duplication that would make subsequent updates difficult.
- **Preservation:** When updating an existing specification, retain valid requirements and established information unless evidence or approved changes justify their revision.

### User Acceptance

Completion of repository inspection and document generation does not constitute acceptance.

- Present the generated or revised specification for user review.
- Summarize significant findings, additions, modifications, removals, and unresolved questions.
- Request clarification or confirmation of consequential discrepancies or uncertain requirements.
- Incorporate user feedback into the document.
- Treat the specification as **proposed until explicitly accepted by the user**.

## 5. Scope and Completion

- Create or update only `docs/specs/SYSTEM_SPEC.md`.
- Do not modify executable code, tests, or configuration.
- Do not create Git commits.
- Review the document against all acceptance criteria before presenting it.
- Report which acceptance criteria are satisfied, unverified, or blocked.
- Identify significant questions requiring user clarification or confirmation.
- Do not declare the task accepted without explicit user confirmation.
