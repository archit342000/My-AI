# Code Issues in the Research Engine (`backend/agents/research.py` and dependencies)

During a thorough scan of the codebase, several issues were found and resolved.

## 1. UnboundLocalError for `follow_up_content`

**File:** `backend/agents/research.py`

**Issue:**
Inside the `_execute_section_reflection_and_write` generator, there is a path where `follow_up_content` was referenced before assignment. Specifically, in the line `yield {"type": "result", "data": (section_text, summary_points, plan_mod, follow_up_content, next_source_id)}`, the `follow_up_content` variable was only assigned under certain conditions. If the "Gap-Filling" conditional didn't set `follow_up_content` or wasn't triggered, the variable would remain undefined, causing a crash when execution reached the final `yield`.

**Resolution:**
Defined `follow_up_content = None` (or `""`) near the start of the function block (specifically right next to `follow_up_buffer = []`) so that it is always in scope when execution reaches the `yield` statement.

## 2. Undefined Variable `log_event` in Utilities

**File:** `backend/utils.py`

**Issue:**
In the `check_url_safety` function, if an exception occurred during the request to the `urlhaus` API, the exception block attempted to call `log_event`. However, `log_event` was not imported from `backend.logger` at the top of the file, leading to an `UnboundLocalError: local variable 'log_event' referenced before assignment` (or `NameError: name 'log_event' is not defined` depending on the Python version).

**Resolution:**
Added `log_event` to the existing import statement: `from backend.logger import log_tool_call, log_llm_call, log_event`.

## 3. Raising NoneType Exception in Thread Runner

**File:** `backend/utils.py`

**Issue:**
In the `run_coro` function block inside `visit_page`, an exception wrapper used a list `ex = [None]` to catch exceptions from a threaded run. The exception raising condition `if ex[0]: raise ex[0]` triggers a pylint `raising-bad-type` warning (E0702) because `NoneType` could theoretically be raised if not handled carefully, though in context it works if `ex[0]` captures a valid Exception.

**Resolution:**
The current code works practically since `ex[0]` will be an `Exception` object when it evaluates to truthy, but pylint highlighted it as a risk.
