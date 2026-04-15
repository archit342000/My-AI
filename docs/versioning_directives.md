# Versioning & Release Directives

This document defines the standards and procedures for versioning, changelog maintenance, and release workflows within the **My-AI** project. All contributors (human and AI) must adhere to these directives to ensure a professional and predictable release cycle.

## 1. Semantic Versioning (SemVer) Application

The project follows [SemVer 2.0.0](https://semver.org/). The version format is `vMAJOR.MINOR.PATCH` (e.g., `v3.1.0`).

| Increment | Type | Criteria | Example |
| :--- | :--- | :--- | :--- |
| **MAJOR** | Breaking Change | Incompatible API changes, major architectural shifts, or complete UI/UX redesigns that break existing user workflows or data structures. | `v2.0.0` (Design Overhaul) |
| **MINOR** | Feature | Adding functionality in a backward-compatible manner (e.g., new tools, new agent capabilities, new UI modules). | `v3.1.0` (New File Reading Infra) |
| **PATCH** | Bug Fix | Backward-compatible bug fixes, security hardening, or minor UI/UX refinements that do not add new capabilities. | `v2.3.1` (Animation Stability) |

## 2. Step-by-Step Version Update Procedure

When a release is prepared, follow these steps in strict order:

### Step 1: Increment Version Variables
Update `backend/version.py` by incrementing the appropriate variable and updating the `VERSION` string.
- **Action**: Modify `VERSION`, `VERSION_MAJOR`, `VERSION_MINOR`, or `VERSION_PATCH`.
- **File**: `backend/version.py`

### Step 2: Update Changelog & README
Append a new entry to the top of `changelog.md` and update the version number in `README.md`.
- **Action**: Determine the scope of changes by inspecting the current branch's diff against the base branch (e.g., `git diff main...HEAD`).
- **Format (Changelog)**: Use the `## vX.Y.Z` header.
- **Format (README)**: Update the version string at the top of the file.
- **Content (Changelog)**: Use bullet points with bolded categories (see *Changelog Standards* below).
- **Mandatory Entry**: Include a `* **Version Bump**: Incremented version globally to vX.Y.Z.` line.

### Step 3: Git Workflow & Tagging
1. **Branch Naming**: Ensure all work related to the version is on a branch following the pattern: `{version}-{description}` (e.g., `3.1.1-fix-auth-leak`).
2. **Commit**: Commit the version changes with a clear message: `chore: bump version to vX.Y.Z`.
3. **Tagging**: Once merged to the main branch, create a git tag:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

## 3. Changelog Standards

All entries in `changelog.md` must be professional, concise, and categorized.

### Entry Format
```markdown
## vX.Y.Z
* **[Category Name]**: [Description of the change/feature].
* **Version Bump**: Incremented version globally to vX.Y.Z.
```

### Categories
Use the following bolded categories to organize changes:
- **Feature**: New capabilities or tools.
- **Bug Fix**: Corrections to existing logic or UI.
- **UX Refinement**: Improvements to user experience, animations, or layout.
- **Architecture**: Significant backend or structural changes (e.g., MCP migration).
- **Security**: Hardening, permission updates, or secret management.
- **Documentation**: Updates to guides, README, or architectural docs.
- **Refactor**: Code improvements that do not change behavior.
- **Cleanup**: Removal of obsolete code, templates, or experimental files.

### Tone & Style
- **Tone**: Technical, objective, and precise. Avoid marketing language (e.g., use "Optimized content flow" instead of "Amazing new flow").
- **Tense**: Use past tense for completed actions (e.g., "Implemented", "Fixed", "Updated").
- **Detail**: Focus on the *what* and *why*. If a change is highly technical (e.g., "Switched ChromaDB to cosine distance"), include the technical detail.

## 4. Summary Checklist for AI Agents

Before concluding a task that requires a version bump, verify:
- [ ] `backend/version.py` matches the `changelog.md` entry.
- [ ] `changelog.md` entries are at the top of the file in descending order.
- [ ] Every changelog entry has a `**Version Bump**` line.
- [ ] The branch name correctly incorporates the version number.
