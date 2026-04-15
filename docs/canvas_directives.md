# Canvas Directives (v3.1.0)

**Note:** This document may contain outdated information. The code is the source of truth. For discrepancies, see `IMPLEMENTATION_DISCREPANCIES.md`.

## Overview

This document defines the canvas architecture, lifecycle operations, versioning system, and best practices for all agents working with canvas functionality.

## Architecture Overview

### Component Location

The canvas system is implemented across multiple modules:
- **`backend/canvas_manager.py`**: Centralized canvas operations.
- **`backend/db_wrapper.py`**: Unified database persistence and row-level caching.
- **`backend/tools.py`**: Tool definitions for LLM interaction (`create_canvas`, `manage_canvas`, etc.).

### Atomic Transaction Model for Canvas

Canvas operations within a single user message form an **atomic transaction**:

```
┌─────────────────────────────────────────────────────────────────┐
│       Canvas Atomic Transaction Flow                            │
├─────────────────────────────────────────────────────────────────┤
│  User Message → Execute All Operations                         │
│    ├── Tool Execution (with retry)                             │
│    ├── Tool Execution (with retry)                             │
│    └── Canvas Creation/Update (with retry)                     │
│                                                                 │
│  If ALL succeed → Success Response                             │
│  If ANY fail → Transaction Fails (no partial success)          │
└─────────────────────────────────────────────────────────────────┘
```

**Rule 1: Canvas operations within a transaction must succeed**

If tools succeed but canvas creation fails, the entire transaction fails:

```python
# Atomic transaction pattern
transaction_success = True

# Execute tools
for tool in tools:
    if not execute_tool(tool):
        transaction_success = False
        break

# Execute canvas operation (only if tools succeeded)
if transaction_success:
    result = create_canvas(...)
    if not result["success"]:
        transaction_success = False
        # Transaction fails - do not report partial success
```

**Rule 2: Canvas component has its own retry mechanism**

Canvas operations retry up to 2 times before failing.

### Canvas Data Model (v2.1.0)

Canvas entities are stored across multiple tables:

```
┌─────────────────────────────────────────────────────────────┐
│              Canvas Data Model (v2.1.0)                     │
├─────────────────────────────────────────────────────────────┤
│  canvases (metadata)                                       │
│  ├── id (TEXT) - Local canvas identifier                   │
│  ├── chat_id (TEXT FK) - Parent chat                      │
│  ├── title (TEXT) - Display title                         │
│  ├── filename (TEXT) - File on disk                       │
│  ├── timestamp (REAL) - Creation time                     │
│  ├── folder (TEXT) - Folder organization                  │
│  ├── tags (TEXT) - JSON array of tags                     │
│  ├── canvas_type (TEXT) - 'custom', 'code', etc.          │
│  └── current_version (INTEGER) - Latest version number     │
│  PRIMARY KEY: (id, chat_id)                                │
│                                                            │
│  canvas_versions (version history)                         │
│  ├── id (INTEGER PK)                                      │
│  ├── canvas_id (TEXT)                                     │
│  ├── chat_id (TEXT)                                       │
│  ├── version_number (INTEGER)                             │
│  ├── content (TEXT) - Markdown content                    │
│  ├── author (TEXT) - Who made the change                  │
│  ├── timestamp (REAL)                                     │
│  └── comment (TEXT) - Version comment                     │
│  FOREIGN KEY: (canvas_id, chat_id) REFERENCES canvases     │
│                                                            │
│  canvas_permissions (access control)                       │
│  ├── id (INTEGER PK)                                      │
│  ├── canvas_id (TEXT)                                     │
│  ├── chat_id (TEXT)                                       │
│  ├── user_id (TEXT)                                       │
│  ├── permission (TEXT) - 'read' or 'write'                │
│  └── timestamp (REAL)                                     │
│  FOREIGN KEY: (canvas_id, chat_id) REFERENCES canvases     │
└─────────────────────────────────────────────────────────────┘
```
```

## Canvas Lifecycle

### Create Canvas

Creates a new canvas with initial content.

```python
from backend.canvas_manager import create_canvas

result = create_canvas(
    chat_id="chat_123",
    canvas_id="my_canvas",
    title="My Document",
    content="# Title\n\nContent here",
    folder="documents",
    tags=["project", "important"],
    author="system",
    version_comment="Initial version"
)
```

**Rule 4: Canvas IDs are unique within a chat**

The `canvas_id` is typically an integer string managed by `db.get_next_canvas_counter(chat_id)`. Composite keys `(id, chat_id)` ensure global uniqueness across different chats.

```python
# Internal ID generation
canvas_id = str(db.get_next_canvas_counter(chat_id))
```

**Rule 5: Always specify title - used for display and export**

```python
# Good
title="Market Analysis Report"

# Bad
title=""
```

### Update Canvas

Updates the entire canvas content. **Requires `chat_id`**.

```python
from backend.canvas_manager import update_canvas_content

result = update_canvas_content(
    canvas_id="1",
    chat_id="chat_123",
    new_content="# Updated Title\n\nNew content",
    author="user",
    version_comment="Major update"
)
```

**Rule 6: Update replaces entire content**

Use `append_to_canvas()` or `patch_canvas_section()` for partial updates.

### Append to Canvas

Adds content to the end of the canvas. **Requires `chat_id`**.

```python
from backend.canvas_manager import append_to_canvas

result = append_to_canvas(
    canvas_id="1",
    chat_id="chat_123",
    content_to_append="\n\n## New Section\n\nContent...",
    author="user"
)
```

**Rule 7: Append adds double newline separator**

Content is automatically separated by `\n\n` from existing content.

### Patch Canvas Section

Replaces a specific section identified by its heading. **Requires `chat_id`**.

```python
from backend.canvas_manager import patch_canvas_section

result = patch_canvas_section(
    canvas_id="1",
    chat_id="chat_123",
    target_section="## Background",
    new_content="## Background\n\nNew background content",
    author="user"
)
```

### Delete Section

Removes a specific section identified by its heading. **Requires `chat_id`**.

```python
from backend.canvas_manager import delete_section

result = delete_section(
    canvas_id="1",
    chat_id="chat_123",
    target_section="## Section to Remove"
)
```

**Rule 6: Delete section removes content and heading**

The targeted section heading and all content below it (until the next equal-or-higher heading) are removed.

**Rule 8: Target section must match heading exactly**

The heading text must match exactly (case-sensitive).

```python
# Good - exact match
target_section="## Background"

# Bad - will not match
target_section="## background"
```

**Rule 6: Patch replaces from target to next section**

The patch replaces content from `target_section` heading to the next heading of equal or higher level.

### Delete Canvas

Deletes a canvas and all its versions.

```python
Deletes a canvas and all its versions. **Requires `chat_id`**.

```python
from backend.canvas_manager import delete_canvas

result = delete_canvas(canvas_id="1", chat_id="chat_123")
```
```

**Rule 7: Deletion is irreversible**

All canvas versions and file content are permanently deleted.

## Version Management

### Version Creation

Every canvas operation creates a version record:

```python
def _create_version_record(canvas_id, content, author, version_comment):
    """Create a version record in the database."""
    # Gets next version number
    version_number = _get_next_version_number(canvas_id) + 1

    # Insert version record
    c.execute(
        "INSERT INTO canvas_versions (canvas_id, chat_id, version_number, content, author, timestamp, comment)",
        (canvas_id, chat_id, version_number, content, author, time.time(), version_comment)
    )
```
```

### Version History

Retrieve all versions of a canvas:

```python
from backend.canvas_manager import get_canvas_versions

versions = get_canvas_versions(canvas_id="1", chat_id="chat_123")
for version in versions:
    print(f"v{version['version_number']}: {version['comment']}")
```

**Rule 8: All versions are preserved**

Canvas versions are never automatically deleted.

## Canvas ID Format

### ID Structure

Canvas IDs use a simple numeric counter format:

```
{counter}
```

The counter is generated by `db.get_next_canvas_counter(chat_id)` and returns incrementing integers starting from 1.

**Example:** `1`, `2`, `3`, etc.

**Rule 9: Canvas IDs are simple numeric counters**

The canvas ID is a simple integer string managed by the database counter. No prefixes or UUIDs are used.

```python
# Internal ID generation
canvas_id = db.get_next_canvas_counter(chat_id)  # Returns "1", "2", "3", etc.
```

**Note:** The old `{type}_{chat_id}_{timestamp}_{uuid}` format is no longer used.

## File Persistence

### File Naming

Canvas files are stored with sanitized filenames:

```python
def generate_canvas_filename(chat_id, canvas_id):
    """Generate safe filename for canvas."""
    safe_chat_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(chat_id))
    safe_canvas_id = sanitize_filename(canvas_id)
    return f"{safe_chat_id}_{safe_canvas_id}.md"
```

**Rule 10: Filenames are sanitized to prevent injection**

Invalid characters are replaced with underscores.

### File Location

Canvas files are stored in:

```
{DATA_DIR}/canvases/{chat_id}_{canvas_id}.md
```

**Rule 11: Ensure CANVASES_DIR exists before operations**

```python
def ensure_canvases_dir():
    os.makedirs(CANVASES_DIR, exist_ok=True)
```

## Search Indexing

### FTS5 Integration

Canvas content is indexed for full-text search using SQLite FTS5.

```python
from backend.db_wrapper import db

db.sync_canvas_search_index(canvas_id, chat_id)
```

**Rule 12: Always sync search index after content changes**

```python
def update_canvas_content(canvas_id, new_content, ...):
    # Update content
    ...

    # Sync index
    db.sync_canvas_search_index(canvas_id, chat_id)
```
```

**Rule 13: FTS5 sync is non-blocking**

FTS5 sync errors should not fail the main operation:

```python
try:
    sync_canvas_search_index(canvas_id)
except Exception as e:
    logging.error(f"FTS5 sync failed: {e}")
```

### Rebuilding Index

Rebuild the entire search index:

```python
from backend.db_wrapper import db

count = db.rebuild_canvas_search_index()
```
```

**Rule 14: Use rebuild when corruption is detected**

```python
from backend.db_wrapper import db

if db.fix_fts5_table():
    log_event("fts5_recovered", {"timestamp": time.time()})
```

## Canvas Modes

### Active Canvas Context

When a canvas is active, its content is injected into the system prompt:

```python
if active_canvas_context and canvas_mode:
    canvas_ctx = f"""
### ACTIVE CANVAS ###
Canvas ID: {active_canvas_context['id']}
Content:
---
{active_canvas_context['content'][:config.CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT]}
---
### END ACTIVE CANVAS ###
"""
```

**Rule 15: Active context is limited to CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT**

Default limit is 32,000 characters to prevent prompt overflow.

### Canvas Inventory

List all canvases for a chat:

```python
from backend.db_wrapper import db

canvases = db.get_chat_canvases(chat_id="chat_123")
for canvas in canvases:
    print(f"{canvas['title']} ({canvas['id']})")
```

**Rule 16: Canvas inventory uses 200 character preview**

```python
content_preview = canvas.get('content', '')[:200] or 'empty'
```

## Tool Interaction

### create_canvas Tool Schema (NEW)

The LLM creates new canvases via the `create_canvas` tool. This is the **only** way to create new canvases.

```python
CREATE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "create_canvas",
        "description": "Creates a new persistent side-panel canvas for documents, code, or data analysis.",
        "parameters": {
            "title": "string (required)",
            "content": "string (required)",
            "canvas_type": "string (optional: 'custom', 'code', 'document')"
        }
    }
}
```

**Usage**:
1. Call `create_canvas` with `title` and `content`
2. System returns generated `canvas_id` in response
3. Use the returned `canvas_id` for subsequent `manage_canvas` operations

### manage_canvas Tool Schema

The LLM manages existing canvases via the `manage_canvas` tool. **Requires explicit `id` field**.

**Note**: The `action='create'` is deprecated. Use `create_canvas` for creating new canvases.

```python
MANAGE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "manage_canvas",
        "description": "Updates or modifies an existing canvas. Always use the numeric 'id' returned by create_canvas.",
        "parameters": {
            "action": "replace | patch | append",
            "id": "string (required)",
            "title": "string (optional)",
            "content": "string (required)",
            "target_section": "string (for patch only)"
        }
    }
}
```

### Action Types

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create` | **Deprecated** - Use `create_canvas` instead | - |
| `replace` | Replace entire content | action, id, content |
| `patch` | Replace section | action, id, content, target_section |
| `append` | Add to end | action, id, content |
| `delete_section` | Remove section | action, id, target_section |

**Rule 17: target_section only valid for patch action**

```python
if action == "patch":
    if not target_section:
        raise ValueError("target_section required for patch action")
```

## Export Functions

### Markdown Export

Export canvas as markdown:

```python
from backend.canvas_manager import export_canvas_markdown

content, filename = export_canvas_markdown(canvas_id="1", chat_id="chat_123")
```
```

### HTML Export

Export canvas as styled HTML:

```python
from backend.canvas_manager import export_canvas_html

html_content, filename = export_canvas_html(canvas_id="1", chat_id="chat_123")
```
```

### PDF Export

Export canvas as PDF:

```python
from backend.canvas_manager import export_canvas_pdf

pdf_bytes, filename = export_canvas_pdf(canvas_id="1", chat_id="chat_123")
```
```

**Rule 18: Use appropriate export format for use case**

- Markdown: For editing, version control
- HTML: For viewing in browser
- PDF: For printing, sharing

## Error Handling

### Canvas Not Found

```python
def update_canvas_content(canvas_id, chat_id, ...):
    canvas_meta = get_canvas_meta(canvas_id, chat_id)
    if not canvas_meta:
        return {"success": False, "error": "Canvas not found"}
```
```

**Rule 19: Always check canvas exists before operations**

### File Errors

```python
def delete_canvas(canvas_id):
    try:
        os.remove(filepath)
    except OSError as e:
        log_event("canvas_delete_file_error", {"canvas_id": canvas_id, "error": str(e)})
```

**Rule 20: File errors are logged but don't fail operation**

Best-effort file deletion - database cleanup still proceeds.

## Canvas Permissions

### Permission Levels

| Permission | Description |
|------------|-------------|
| `read` | Can view canvas |
| `write` | Can edit canvas |

### Check Permission

```python
from backend.canvas_manager import check_canvas_permission

has_write = check_canvas_permission(
    canvas_id="1",
    chat_id="chat_123",
    user_id="user_123",
    required_permission="write"
)
```
```

**Rule 21: Default permission is 'write'**

New permissions are created with 'write' level unless specified.

### Share Canvas

```python
from backend.canvas_manager import share_canvas

result = share_canvas(
    canvas_id="1",
    chat_id="chat_123",
    user_id="user_456",
    permission="read"
)
```
```

## Best Practices

### 1. Use Descriptive Titles

```python
# Good
title="Q4 Market Analysis Report - November 2024"

# Bad
title="Untitled Canvas"
```

### 2. Provide Meaningful Version Comments

```python
# Good
version_comment="Added competitive analysis section"

# Bad
version_comment="update"
```

### 3. Use Folders for Organization

```python
# Good
folder="reports/q4-2024"

# Bad
folder=""
```

### 4. Tag Important Canvases

```python
# Good
tags=["important", "client-facing", "q4-2024"]

# Bad
tags=[]
```

### 5. Patch with Exact Heading Matches

```python
# Good - exact match
patch_canvas_section(canvas_id, "## Background", new_content)

# Bad - case mismatch won't work
patch_canvas_section(canvas_id, "## background", new_content)
```

### 6. Sync Index After Updates

```python
# Always sync after content changes
update_canvas_content(canvas_id, new_content)
sync_canvas_search_index(canvas_id)
```

### 7. Use Append for Additions, Patch for Replacements

```python
# Add new sections
append_to_canvas(canvas_id, "\n\n## New Section\n\nContent")

# Replace existing sections
patch_canvas_section(canvas_id, "## Outdated Section", new_content)
```

## Functions Reference

### Core Operations

| Function | Purpose | Returns |
|----------|---------|---------|
| `create_canvas(...)` | Create new canvas | Dict with success, canvas_id |
| `get_canvas_content(canvas_id)` | Get canvas content | str or None |
| `update_canvas_content(...)` | Update entire content | Dict with version_id |
| `append_to_canvas(...)` | Append to end | Dict with version_id |
| `patch_canvas_section(...)` | Patch section | Dict with version_id, section_replaced |
| `delete_canvas(canvas_id)` | Delete canvas | Dict with success |

### Metadata Operations

| Function | Purpose | Returns |
|----------|---------|---------|
| `get_canvas_meta(canvas_id, chat_id)` | Get metadata | Dict or None |
| `get_chat_canvases(chat_id)` | List canvases | List of Dicts |
| `get_chat_canvases_with_details(...)` | List with details | List of Dicts |
| `save_canvas_meta(...)` | Save metadata | None |

### Version Operations

| Function | Purpose | Returns |
|----------|---------|---------|
| `get_canvas_versions(canvas_id, chat_id)` | Get versions | List of Dicts |
| `restore_canvas_version(cid, mid, vid)` | Restore version | Dict |

### Export Operations

| Function | Purpose | Returns |
|----------|---------|---------|
| `export_canvas_markdown(cid, mid)` | Export as markdown | (content, filename) |
| `export_canvas_html(cid, mid)` | Export as HTML | (html, filename) |
| `export_canvas_pdf(cid, mid)` | Export as PDF | (bytes, filename) |

### Permission Operations

| Function | Purpose | Returns |
|----------|---------|---------|
| `check_canvas_permission(...)` | Check access | bool |
| `share_canvas(...)` | Share canvas | Dict |
| `revoke_permission(...)` | Revoke access | Dict |

## Appendix: Complete Canvas Workflow

```python
from backend.db_wrapper import db

# 1. Create canvas
result = create_canvas(
    chat_id="chat_123",
    title="My Report",
    content="# Title\n\nInitial content",
    folder="reports",
    tags=["important"]
)
canvas_id = result["canvas_id"]  # numeric string e.g. "1"

# 2. Append content
append_to_canvas(
    canvas_id=canvas_id,
    chat_id="chat_123",
    content_to_append="\n\n## Section 2\n\nMore content"
)

# 3. Patch a section
patch_canvas_section(
    canvas_id=canvas_id,
    chat_id="chat_123",
    target_section="## Section 1",
    new_content="## Section 1\n\nUpdated content"
)

# 4. Get content
content = get_canvas_content(canvas_id, chat_id="chat_123")

# 5. Update entire content
update_canvas_content(
    canvas_id=canvas_id,
    chat_id="chat_123",
    new_content="# Completely New Title\n\nNew content"
)

# 6. Sync search index
db.sync_canvas_search_index(canvas_id, chat_id="chat_123")

# 7. Delete when done
delete_canvas(canvas_id, chat_id="chat_123")
```
