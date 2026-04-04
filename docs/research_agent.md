# Research Agent Directives

## Overview

This document defines the research agent architecture, conversation management patterns, step-by-step execution flow, and canvas integration rules. The research agent is the **exception** to the atomic operation model - it is a long-running, multi-phase process.

## Architecture Overview

### Component Location

The research agent is implemented in:
- **`backend/agents/research.py`**: Main research pipeline
- **`backend/agents/research_schemas.py`**: JSON schemas for structured outputs
- **`backend/agents/research_utils.py`**: Utility functions for research operations
- **`backend/prompts.py`**: All research-specific system prompts

### Research Agent Exception

**Rule 1: Research agent is the ONLY NON-ATOMIC operation**

Unlike all other operations, the research agent:
- Is a long-running, multi-phase process (can take minutes)
- Does NOT follow the atomic operation model
- Uses sequential step execution with reflection
- Has its own persistence and state management
- Partial success is expected and reported during execution
- Is documented separately from atomic tools

**All other operations (tools, canvas, chat responses) must follow the atomic transaction model.**

### High-Level Phases

```
┌─────────────────────────────────────────────────────────────┐
│           Research Agent Phases                            │
├─────────────────────────────────────────────────────────────┤
│  Phase 0: Scout                                            │
│    - Analyze topic context                                 │
│    - Identify knowledge gaps                               │
│    - Recommend preliminary searches                        │
│                                                            │
│  Phase 1: Planning                                         │
│    - Generate research plan (XML)                          │
│    - Define sections and queries                           │
│    - Validate plan structure                               │
│                                                            │
│  Phase 2: Section Execution                                │
│    For each section:                                       │
│      - Reflect (gap analysis)                              │
│      - Triage (extract core facts)                         │
│      - Write (draft section)                               │
│      - Summary (generate summary points)                   │
│                                                            │
│  Phase 3: Assembly & Audit                                 │
│    - Stitch sections together                              │
│    - Detect issues (Detective/Auditor)                     │
│    - Fix issues (Surgeon)                                  │
│    - Synthesize conclusions                                │
│    - Normalize citations                                   │
│                                                            │
│  Phase 4: Canvas Integration                               │
│    - Persist final report to canvas                        │
│    - Update UI with complete report                        │
└─────────────────────────────────────────────────────────────┘
```

## Phase 0: Scout

### Purpose

Analyze the research topic before planning to identify context, knowledge gaps, and recommend preliminary searches.

### Scout Flow

```
User Query → Scout Analysis → Clarifying Questions OR Preliminary Search → Planning
```

**Rule 2: Scout may request clarification**

If the topic is ambiguous, the scout will ask clarifying questions:

```python
# Scout returns clarifying_question
if scout_analysis.get("clarifying_question"):
    yield f"data: {clarifying_question}"
    yield "data: [DONE]\n\n"
    return  # Stop and wait for user response
```

### Scout JSON Schema

```python
SCOUT_JSON_SCHEMA = {
    "name": "scout_analysis",
    "schema": {
        "type": "object",
        "properties": {
            "clarifying_question": "str (optional)",  # If topic needs clarification
            "needs_search": "bool",                   # Whether preliminary search needed
            "preliminary_search": {
                "query": "str",
                "topic": "str",
                "time_range": "str"
            },
            "structural_recommendation": "str"  # Narrative, table, list, etc.
        }
    }
}
```

### Scout History Persistence

Scout conversation history is saved to disk for resume capability:

```python
scout_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_scout_history.json")
```

**Rule 3: Check scout history before starting**

If history exists and scout is complete, skip to planning:

```python
if os.path.exists(scout_history_path):
    # Load and check if scout is done
    if scout_done:
        # Skip to planning phase
```

## Phase 1: Planning

### Purpose

Generate a structured research plan defining sections, descriptions, and queries.

### Planning Flow

```
Scout Output → Planner → Research Plan (XML) → Validation → Execution
```

### Planning JSON Schema

```python
PLANNER_JSON_SCHEMA = {
    "name": "research_plan",
    "schema": {
        "type": "object",
        "properties": {
            "title": "str",  # Report title
            "sections": [
                {
                    "heading": "str",     # Section heading
                    "description": "str",  # Section description
                    "queries": [
                        {
                            "search": "str",      # Query to search
                            "topic": "str",       # Search topic
                            "time_range": "str",  # Time range filter
                            "start_date": "str",
                            "end_date": "str"
                        }
                    ]
                }
            ]
        }
    }
}
```

### Plan Validation

**Rule 4: Plan must be validated before execution**

```python
from backend.utils import validate_research_plan

if not validate_research_plan(plan_text):
    # Retry plan generation
    yield f"data: {create_chunk(model, content='**Plan validation failed.**')}\n\n"
```

### Plan as Markdown

Plans are formatted as markdown for UI display:

```python
def _format_plan_as_markdown(xml_plan):
    """Converts a <research_plan> XML string into a readable Markdown preview."""
    # Parses XML and formats as markdown
    # Shows sections, headings, descriptions, and queries
```

## Phase 2: Section Execution

### Purpose

For each section in the plan, execute a multi-turn conversation to research, reflect, write, and summarize.

### Section Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│        Section Execution (Per Section)                     │
├─────────────────────────────────────────────────────────────┤
│  TURN 1: Reflection (Gap Analysis)                         │
│    - Analyze search findings                               │
│    - Identify knowledge gaps                               │
│    - Recommend follow-up queries                           │
│                                                            │
│  TURN 2 (conditional): Gap-Filling                         │
│    - Execute follow-up queries                             │
│    - Gather additional content                             │
│                                                            │
│  TURN 2.5: Triage                                          │
│    - Extract core facts                                    │
│    - Validate uniqueness                                   │
│    - Cap at MAX_FACTS (25)                                 │
│                                                            │
│  TURN 3: Writing                                           │
│    - Draft section content                                 │
│    - Include citations                                     │
│    - Follow structure guidelines                           │
│                                                            │
│  TURN 4: Summary                                           │
│    - Generate summary points                               │
│    - For next sections only                                │
└─────────────────────────────────────────────────────────────┘
```

### Search-Level Operations

For each query in a section:

1. **Search**: Execute Tavily search
2. **Select**: Choose top URLs (configurable count)
3. **Extract**: Extract content with budget limits
4. **Deep Mode**: Map sub-pages for additional context

**Rule 5: Content budget limits per query**

```python
# Regular mode: 50,000 chars (~12,500 tokens)
content_budget = config.RESEARCH_CONTENT_BUDGET_REGULAR

# Deep mode: 80,000 chars (~20,000 tokens)
content_budget = config.RESEARCH_CONTENT_BUDGET_DEEP
```

### Source Registry

All sources are tracked in a global registry:

```python
source_registry = {
    1: {"url": "https://example.com", "title": "Example"},
    2: {"url": "https://another.com", "title": "Another"},
    # ...
}
```

**Rule 6: Sources are globally tracked across all sections**

This enables:
- Consistent citation numbering
- Reference generation at the end
- Duplicate detection

### Section Reflection

The reflection phase analyzes findings and identifies gaps:

```python
# Reflection JSON schema
REFLECTION_JSON_SCHEMA = {
    "name": "reflection",
    "schema": {
        "type": "object",
        "properties": {
            "gaps": [
                {
                    "query": "str",
                    "justification": "str",
                    "importance": "str"
                }
            ],
            "plan_modification": {
                "additions": [...],
                "removals": [...]
            }
        }
    }
}
```

**Rule 7: Reflection may modify the plan**

Sections can be added or removed based on findings:

```python
if plan_mod and isinstance(plan_mod, dict):
    for addition in plan_mod.get('additions', []):
        new_heading = addition.get('heading', '')
        if new_heading:
            sections.append({...})
            n_sections = len(sections)
```

### Section Triage

Extracts core facts from gathered content:

```python
TRIAGE_JSON_SCHEMA = {
    "name": "triage",
    "schema": {
        "type": "object",
        "properties": {
            "core_facts": [
                {
                    "fact": "str",
                    "sources": [int],  # Source IDs
                    "confidence": "str"
                }
            ]
        }
    }
}
```

**Rule 8: Triage caps facts at MAX_FACTS (25)**

```python
triage_result["core_facts"] = unique_valid_facts[:config.RESEARCH_TRIAGE_MAX_FACTS]
```

### Section Writing

Drafts the section content with citations:

```python
WRITER_JSON_SCHEMA = {
    "name": "section_draft",
    "schema": {
        "type": "object",
        "properties": {
            "markdown_content": "str",  # Section in markdown
            "citations_used": [int]
        }
    }
}
```

**Rule 9: Writers must cite sources**

All factual claims should include citations like `[Source 1]`, `[Source 2]`.

### Section Summary

Generates summary points for subsequent sections:

```python
SUMMARY_JSON_SCHEMA = {
    "name": "section_summary",
    "schema": {
        "type": "object",
        "properties": {
            "summary_points": [
                "str",  # Key insight from this section
                "str"
            ]
        }
    }
}
```

**Rule 10: Summary is only generated for non-final sections**

Final sections don't generate summaries since there are no subsequent sections.

### Entity Glossary

Entities and terms are tracked across sections:

```python
entity_glossary = {
    "AI": "Artificial Intelligence",
    "LLM": "Large Language Model",
    # ...
}
```

**Rule 11: Entity glossary persists across sections**

This ensures consistent terminology throughout the report.

## Phase 3: Assembly & Audit

### Purpose

Assemble all sections into a complete report, audit for quality issues, and synthesize conclusions.

### Assembly Steps

1. **Validate Citations**: Remove invalid citation tags
2. **Stitch Sections**: Combine all sections
3. **Strip Images**: Remove image placeholders
4. **Detect Issues**: Run Auditor (Detective)
5. **Fix Issues**: Run Surgeon on problematic sections
6. **Synthesize**: Add comparative analysis and takeaways
7. **Normalize Citations**: Ensure consistent citation format
8. **Generate References**: Create references section

### Auditor (Detective)

The Auditor identifies quality issues:

```python
DETECTIVE_JSON_SCHEMA = {
    "name": "report_audit",
    "schema": {
        "type": "object",
        "properties": {
            "issues": [
                {
                    "section_id": int,
                    "type": "str",
                    "severity": "High|Medium|Low",
                    "description": "str"
                }
            ]
        }
    }
}
```

**Rule 12: Auditor severity thresholds are configurable**

```python
# Configurable limits
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999  # Fix all high severity
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5  # Cap at 5 medium
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3     # Cap at 3 low
```

### Surgeon

The Surgeon fixes identified issues:

```python
SURGEON_JSON_SCHEMA = {
    "name": "section_patch",
    "schema": {
        "type": "object",
        "properties": {
            "patched_markdown": "str",  # Corrected section
            "explanation": "str"
        }
    }
}
```

**Rule 13: Surgeon is only invoked for sections with issues**

```python
if audit_result and isinstance(audit_result, dict):
    issues = audit_result.get("issues", [])
    sections_to_rewrite = [...]  # Filtered by severity
    for section_id, section_title, sec_issues in sections_to_rewrite:
        # Surgeon fixes this section
```

### Synthesis

Generates comparative analysis and key takeaways:

```python
SYNTHESIS_JSON_SCHEMA = {
    "name": "report_synthesis",
    "schema": {
        "type": "object",
        "properties": {
            "comparative_analysis": "str",  # Analysis across sections
            "key_takeaways": "str"          # Main conclusions
        }
    }
}
```

**Rule 14: Synthesis is added after all sections**

The synthesis adds a comparative analysis section and key takeaways section.

### Citation Normalization

Normalizes all citations and generates references:

```python
def _normalize_citations(full_report, source_registry):
    """
    Ensures all [Source N] tags are valid.
    Generates References section.
    Returns: (normalized_report, references_list)
    """
```

**Rule 15: All citations must reference valid sources**

Invalid citations are stripped before final output.

## Phase 4: Canvas Integration

### Purpose

Persist the final report to the canvas system for UI display and persistence.

### Canvas Integration Flow

```
Final Report → Update Canvas → UI Update → DONE
```

### Progressive Canvas Updates

During section execution, the canvas is updated progressively:

```python
# First section - create canvas
if section_idx == 0:
    create_canvas(
        chat_id=chat_id,
        canvas_id=f"research_{chat_id}",
        title="Research Report",
        content=f"## {heading}\n\n{section_text}",
        folder="research",
        author="system"
    )

# Subsequent sections - append
else:
    append_to_canvas(
        canvas_id=f"research_{chat_id}",
        content=f"\n\n## {heading}\n\n{section_text}",
        author="system"
    )
```

**Rule 16: Canvas is updated after every section**

This enables:
- Progressive UI rendering
- Partial report recovery on interruption
- Real-time report building

### Final Canvas Update

At the end of Phase 3, the complete report is persisted:

```python
canvas_id = f"research_{chat_id}" if chat_id else "research_report"
canvas_title = f"Research: {report_title[:40]}"

update_canvas_content(
    canvas_id=canvas_id,
    content=full_report,
    author="system",
    version_comment="Final report completed"
)
```

**Rule 17: Final canvas update replaces all progressive content**

The complete report replaces the progressive sections.

### UI Canvas Update Event

The UI receives a special event for canvas updates:

```python
yield f"data: {json.dumps({
    '__canvas_update__': {
        'id': canvas_id,
        'title': canvas_title,
        'content': full_report,
        'action': 'create'
    }
})}\n\n"
```

### Canvas ID Format

Research canvases use a consistent format:

```
research_{chat_id}
```

**Rule 18: Canvas ID includes full chat_id**

This ensures uniqueness even with shared chat_id prefixes.

## Conversation Management

### Main Conversation vs Step Conversations

The research agent maintains **two conversation contexts**:

1. **Main Conversation**: The user's original chat history
2. **Step Conversations**: Internal conversations for each research phase

### Main Conversation Handling

**Rule 19: Main conversation is read-only for research**

The research agent reads from the main conversation but does not modify it:

```python
# Read user queries from main conversation
for m in messages:
    if m['role'] == 'user':
        original_query = m['content']
        break
```

### Step Conversation Management

Each phase has its own conversation context:

#### Scout Conversation

```python
scout_messages = [
    {"role": "system", "content": RESEARCH_SCOUT_PROMPT},
    {"role": "user", "content": original_query}
]
```

#### Planner Conversation

```python
planner_messages = [
    {"role": "system", "content": RESEARCH_PLANNER_PROMPT},
    {"role": "user", "content": scout_output or user_query}
]
```

#### Section Conversation (Per Section)

```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": f"Data for {heading}:\n{content_payload}"}
]

# Turns are appended:
messages.append({"role": "assistant", "content": raw_response})
messages.append({"role": "user", "content": next_prompt})
```

### Conversation State Persistence

Research state is persisted to disk for resume capability:

```python
state_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_state.json")

state = {
    "accumulated_summaries": [...],
    "source_registry": {...},
    "global_source_id": int,
    "last_completed_section": int,
    "structural_recommendation": str,
    "entity_glossary": {...}
}

with open(state_path, "w") as f:
    json.dump(state, f)
```

**Rule 20: State is saved after each section**

This enables:
- Resume after interruption
- Partial report recovery
- Long-running research continuation

### Resume Capability

Research can be resumed from any phase:

```python
# Check for resume state
if resume_state:
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            saved = json.load(f)
        # Restore state
        accumulated_summaries = saved.get("accumulated_summaries", [])
        # ... restore other state
```

**Rule 21: Resume state can be any phase**

Valid resume states:
- `scouting`: Resume Scout phase
- `planning`: Resume Planning phase
- `section_execution`: Resume Section execution
- `assembly`: Resume Assembly phase

## Tool Integration

### manage_canvas Tool for Research

The `manage_canvas` tool is used for research report integration:

```python
MANAGE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "manage_canvas",
        "description": "Manages a persistent side-panel canvas...",
        "parameters": {
            "action": "create | replace | patch | append",
            "id": "string",
            "title": "string",
            "content": "string",
            "target_section": "string (for patch)"
        }
    }
}
```

### Canvas Actions for Research

**Rule 22: Research uses specific canvas actions**

| Action | When Used | Purpose |
|--------|-----------|---------|
| `create` | First section | Create research report canvas |
| `append` | Subsequent sections | Add section to report |
| `replace` | Final report | Replace with complete report |

### Progressive vs Final Canvas

**Rule 23: Distinguish progressive vs final canvas updates**

- **Progressive**: Each section updates canvas incrementally
- **Final**: Complete report replaces progressive content

```python
# Progressive (during section execution)
if section_idx == 0:
    create_canvas(...)
else:
    append_to_canvas(...)

# Final (after all sections)
update_canvas_content(canvas_id, chat_id, full_report, author="system", version_comment="Final report completed")
```

## Error Handling

### Retry Mechanism

Each step (Reflection, Triage, Writing, Summary) has a 3-attempt retry:

```python
for attempt in [1, 2, 3]:
    try:
        result = execute_step()
        if result and valid(result):
            break
    except Exception as e:
        if attempt == 3:
            raise  # Last attempt, re-raise
        continue  # Retry
```

### Meander Detection

If the LLM "meanders" (too much thinking, too little content), the attempt is retried:

```python
if packet.get("meandered") and attempt == 1:
    # Retry with structured mode
    continue
```

**Rule 24: Meander detection thresholds are phase-specific**

```python
# All meander detection thresholds (TOKENS)
RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_TRIAGE_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS = 5000
RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS_TOKENS = 3750
RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS = 1000
RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS = RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS
```

### Transient Error Handling

Transient errors (network timeouts, API rate limits) trigger an automatic retry.

## Resilience & Fallbacks

### Rule 25: Triage and Writer Retries (ValueError)
If the LLM produces malformed output or fails to extract facts during the **Triage** or **Writing** phases, the system triggers a `ValueError`. This initiates an automated retry mechanism (up to 3 attempts) with a fallback to a more structured prompt if the standard reasoning path meanders.

### Rule 26: Section Recovery
If a specific section fails entirely after all retries, the research agent:
1. Logs the failure to `network_index.jsonl`.
2. Marks the section as "Incomplete/Failed" in the task state.
3. Proceeds to the next section rather than crashing the entire research task.
4. Alerts the user in the final report synthesis that certain sections were restricted due to technical errors.

**Rule 27: Non-transient errors fail immediately**

Non-transient errors (validation failures, schema errors) do not retry.

## Configuration

### Key Configuration Values

```python
# Section limits
RESEARCH_MAX_QUERIES_PER_SECTION = 2
RESEARCH_MAX_TOTAL_QUERIES = 10
RESEARCH_MAX_GAPS_PER_SECTION = 2

# Content limits
RESEARCH_CONTENT_BUDGET_REGULAR = 50000
RESEARCH_CONTENT_BUDGET_DEEP = 80000
RESEARCH_CONTENT_CHUNK_LIMIT = 15000

# Triage limits
RESEARCH_TRIAGE_MAX_FACTS = 25

# Audit limits
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3

# Meander detection (TOKENS)
RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_TRIAGE_TOKENS = 2500
RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS = 5000
RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY_TOKENS = 1500
RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS_TOKENS = 3750
RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS = 1000
RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS = RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS
```

**Rule 26: All configuration is in config.py**

Agents should read configuration from `backend.config`, not hardcoded values.

## Best Practices

### 1. Always Check for Clarifying Questions

```python
if scout_analysis.get("clarifying_question"):
    # Stop and ask for clarification
    return
```

### 2. Persist State Frequently

```python
# After each section
with open(state_path, "w") as f:
    json.dump(state, f)
```

### 3. Handle Plan Modifications Gracefully

```python
if plan_mod and isinstance(plan_mod, dict):
    # Add/remove sections as needed
    pass
```

### 4. Validate Before Proceeding

```python
if not validate_research_plan(plan_text):
    # Retry plan generation
    pass
```

### 5. Use Proper Canvas Actions

```python
# Progressive: create/append
# Final: replace
```

### 6. Log Research Events

```python
log_event("research_start", {...})
log_event("research_complete", {...})
log_event("research_section_added", {...})
```

## Functions Reference

### Main Entry Point

| Function | Purpose | Returns |
|----------|---------|---------|
| `generate_research_response(...)` | Main research pipeline | SSE generator |
| `_execute_section_reflection_and_write(...)` | Execute a single section | SSE generator |
| `_format_plan_as_markdown(xml_plan)` | Format plan as markdown | str |

### Utility Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `validate_research_plan(xml_plan)` | Validate plan structure | bool |
| `_is_transient_error(e)` | Check if error is transient | bool |
| `_get_sampling_params(attempt)` | Get sampling parameters | dict |
| `_extract_json_from_text(text)` | Extract JSON from text | dict or None |
| `_execute_mcp_tool(client, tool, args, chat_id)` | Execute MCP tool | result |

### Research Step Functions

| Function | Phase | Purpose |
|----------|-------|---------|
| Scout | Phase 0 | Context analysis |
| Planner | Phase 1 | Plan generation |
| Reflection | Phase 2 | Gap analysis |
| Triage | Phase 2 | Fact extraction |
| Writing | Phase 2 | Section drafting |
| Summary | Phase 2 | Summary generation |
| Detective | Phase 3 | Issue detection |
| Surgeon | Phase 3 | Issue fixing |
| Synthesis | Phase 3 | Conclusion generation |

## Appendix: Complete Research Flow

```python
async def complete_research_flow():
    # Phase 0: Scout
    scout_analysis = await run_scout(topic)
    if scout_analysis.get("clarifying_question"):
        return  # Ask for clarification

    # Phase 1: Planning
    plan = await run_planner(scout_analysis)
    if not validate_research_plan(plan):
        raise ValueError("Invalid plan")

    # Phase 2: Section Execution
    for section in plan["sections"]:
        # Reflection
        reflection = await run_reflection(section)

        # Gap-filling (if needed)
        if reflection["gaps"]:
            await run_gap_filling(reflection["gaps"])

        # Triage
        triage = await run_triage(section)

        # Writing
        section_text = await run_writing(section, triage)

        # Summary (if not final)
        if section_is_not_final:
            summary = await run_summary(section_text)

        # Save state
        save_state(section_index, section_text, summary)

    # Phase 3: Assembly & Audit
    report = assemble_sections()
    audit = await run_auditor(report)
    if audit["issues"]:
        await run_surgeon(audit["issues"])
    report = apply_fixes(report)

    # Synthesis
    synthesis = await run_synthesis(report)
    report += synthesis

    # Finalize
    report = normalize_citations(report)

    # Add References section (automatically generated)
    if references_list:
        report += "\n\n## References\n" + "\n".join(references_list)
    else:
        report += "\n\n## References\nNo external citations were used in this report.\n"

    # Phase 4: Canvas Integration
    update_canvas(canvas_id, report)

    return report
```
