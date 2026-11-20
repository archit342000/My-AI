# --- Event Markers (used by _emit_event and _parse_section_state) ---
# EVENT_SYNTHESIS_START (and the literal 'Synthesizing final report sections...' in agent.py) are compared against stored rows on
# resume, so they keep their exact text; the other status texts are only shown and use the ellipsis character.
EVENT_SCOUT_START = "Starting research topic analysis…"
EVENT_SCOUT_FINALIZED = "Scouting finalized. Context gathered."
EVENT_PLAN_START = "Starting research plan generation…"
EVENT_PLAN_APPROVED = "Research plan approved. Proceeding to execution."
EVENT_ALL_SECTIONS_DONE = "All research sections executed."
EVENT_SECTION_PREFIX = "Section "
EVENT_SECTION_START_PREFIX = "Starting Execution: Section "  # + str(idx)
EVENT_SECTION_COMPLETE_SUFFIX = " complete."                 # "Section N complete."
EVENT_INITIAL_SEARCHES_PREFIX = "Running pre-planned searches for section "
EVENT_INITIAL_SEARCHES_DONE = "Initial Searches Completed."
EVENT_REFLECTION_START = "Starting Reflection: Analyzing gathered data…"
EVENT_REFLECTION_DONE = "Reflection Phase Completed."
EVENT_GAP_SEARCHES_START = "Starting Gap Searches: Filling information voids…"
EVENT_GAP_SEARCHES_IN_PROGRESS = "Running follow-up gap searches…"
EVENT_GAP_SEARCHES_DONE = "Gap Searches Phase Completed."
EVENT_TRIAGE_START = "Starting Triage: Extracting core facts…"
EVENT_TRIAGE_DONE = "Triage Phase Completed."
EVENT_WRITER_START = "Starting Writer: Drafting section narrative…"
EVENT_WRITER_DONE = "Writer Phase Completed."
EVENT_SUMMARY_START = "Starting Summary: Distilling key points…"
EVENT_SUMMARY_DONE = "Summary Phase Completed."
EVENT_SYNTHESIS_START = "Compiling Final Report from Section Data..."
EVENT_SYNTHESIS_POST = "Applying post-processing (citations and formatting) to FileSystem…"
EVENT_RESEARCH_COMPLETE = "Research complete! The full report has been audited and finalized in the FileSystem."

# --- Approval Signal (used in MCQ creation and approval check) ---
PLAN_APPROVAL_SIGNAL = "Yes, proceed"
