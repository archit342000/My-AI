import os
from dotenv import load_dotenv

load_dotenv()

def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

DATA_DIR = get_secret("DATA_DIR", "./backend/data")
os.makedirs(DATA_DIR, exist_ok=True)

# =============================================================================
# AUTHENTICATION
# =============================================================================
# Identity provider: "cloudflare_access" (default, verifies the Access JWT) or "static"
# (development only: every request is the user AUTH_STATIC_EMAIL, no verification).
AUTH_PROVIDER = get_secret("AUTH_PROVIDER", "cloudflare_access").strip().lower()
# Cloudflare Access team domain host (e.g. "myteam.cloudflareaccess.com") and application AUD tag.
CF_ACCESS_TEAM_DOMAIN = get_secret("CF_ACCESS_TEAM_DOMAIN", "").strip().lower()
CF_ACCESS_AUD = get_secret("CF_ACCESS_AUD", "").strip()
# Email of the admin user seeded by init_db().
ADMIN_EMAIL = get_secret("ADMIN_EMAIL", "").strip().lower()
# Email used by the static provider; defaults to the admin.
AUTH_STATIC_EMAIL = get_secret("AUTH_STATIC_EMAIL", "").strip().lower() or ADMIN_EMAIL

AUTH_PROVIDERS = ("cloudflare_access", "static")


def validate_auth_config():
    """Raise ValueError if the auth settings are unusable. Called when the app is imported."""
    if AUTH_PROVIDER not in AUTH_PROVIDERS:
        raise ValueError(f"AUTH_PROVIDER must be one of {AUTH_PROVIDERS}, got {AUTH_PROVIDER!r}")
    if not ADMIN_EMAIL:
        raise ValueError("ADMIN_EMAIL is required")
    if AUTH_PROVIDER == "cloudflare_access":
        if not CF_ACCESS_TEAM_DOMAIN:
            raise ValueError("CF_ACCESS_TEAM_DOMAIN is required when AUTH_PROVIDER=cloudflare_access")
        if any(ch in CF_ACCESS_TEAM_DOMAIN for ch in "/:") or any(ch.isspace() for ch in CF_ACCESS_TEAM_DOMAIN):
            raise ValueError("CF_ACCESS_TEAM_DOMAIN must be a bare host such as myteam.cloudflareaccess.com (no scheme, port, path or spaces)")
        if not CF_ACCESS_AUD:
            raise ValueError("CF_ACCESS_AUD is required when AUTH_PROVIDER=cloudflare_access")
    elif not AUTH_STATIC_EMAIL:
        raise ValueError("AUTH_STATIC_EMAIL is required when AUTH_PROVIDER=static")

# Which UI Flask serves at "/": "react" (frontend/dist/, default) or "legacy" (static/).
# The legacy UI stays reachable at /legacy/ in both modes.
FRONTEND = os.getenv("FRONTEND", "react").strip().lower()
if FRONTEND not in ("legacy", "react"):
    raise ValueError(f"FRONTEND must be 'legacy' or 'react', got {FRONTEND!r}")

# =============================================================================
# AI INFERENCE & INFRASTRUCTURE
# =============================================================================
AI_PROXY_URL = get_secret("AI_PROXY_URL", "http://localhost:5001")


PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() == "true"
# Per-user rate limits (backend/auth/rate_limit.py): turn starts (send and resume) per minute, web searches per day.
# Zero or less means unlimited. The admin is exempt unless RATE_LIMIT_EXEMPT_ADMIN is false.
RATE_LIMIT_TURNS_PER_MINUTE = int(os.getenv("RATE_LIMIT_TURNS_PER_MINUTE", "10"))
RATE_LIMIT_SEARCHES_PER_DAY = int(os.getenv("RATE_LIMIT_SEARCHES_PER_DAY", "200"))
RATE_LIMIT_EXEMPT_ADMIN = os.getenv("RATE_LIMIT_EXEMPT_ADMIN", "True").lower() == "true"
CHROMA_PATH = get_secret("CHROMA_PATH", os.path.abspath(os.path.join(DATA_DIR, "chroma_db")))

# Ensure persistence directories exist
os.makedirs(CHROMA_PATH, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs", "general"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "tasks"), exist_ok=True)

# =============================================================================
# SEARCH (Tavily API)
# =============================================================================
# TAVILY_API_KEY is loaded from environment/secrets for documentation compliance
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

MAX_SEARCH_RESULTS = 5

# =============================================================================
# NETWORK & INTEGRATION TIMEOUTS (seconds)
# =============================================================================
TIMEOUT_LLM_ASYNC = None           # Parallel AI generation tasks
TIMEOUT_EMBEDDING = int(os.getenv("TIMEOUT_EMBEDDING", 1800))       # Max seconds for an embedding request
INFERENCE_PARALLELISM = int(os.getenv("INFERENCE_PARALLELISM", 1)) # Max concurrent LLM requests
TIMEOUT_TAVILY_SEARCH_ASYNC = 60   # Async search
TIMEOUT_MCP_TOOL_CALL = int(os.getenv("TIMEOUT_MCP_TOOL_CALL", 300))    # Max seconds for any MCP tool call (e.g. Playwright deep scrape)
TIMEOUT_LLM_STREAM_READ = int(os.getenv("TIMEOUT_LLM_STREAM_READ", 1800))  # Max seconds between LLM tokens before dropping stream (must accommodate large prefills)
# FileSystem channel acquire timeout (seconds) — prevents permanent hang if holder crashes
FILE_SYSTEM_CHANNEL_ACQUIRE_TIMEOUT = int(os.getenv("FILE_SYSTEM_CHANNEL_ACQUIRE_TIMEOUT", 30))
# How long stop, delete and clear-all wait (seconds) for a running turn's worker to exit before they answer
TASK_STOP_WAIT_SECONDS = float(os.getenv("TASK_STOP_WAIT_SECONDS", 5))
# Subscriber poll interval (seconds) — how often subscribe() checks if the task is still alive
SUBSCRIBER_POLL_INTERVAL = float(os.getenv("SUBSCRIBER_POLL_INTERVAL", 5.0))

# =============================================================================
# WEB EXTRACTION & PARSING
# =============================================================================
MAX_CHARS_VISIT_PAGE = 40000        # Character cap for standard visit_page tool
# Minimum content length thresholds (chars) to accept extraction as valid
RESEARCH_EXTRACT_MIN_RAW_CONTENT = 50       # Raw content from Tavily search results
RESEARCH_EXTRACT_MIN_PDF_CONTENT = 100      # PDF extraction via pymupdf
RESEARCH_EXTRACT_MIN_TAVILY_CONTENT = 100   # Tavily Extract API fallback
RESEARCH_MAP_MIN_CONTENT = 100              # Deep-mode mapped sub-pages
RESEARCH_CONTENT_MIN_LENGTH_REGULAR = 50    # Direct HTTP GET (regular mode)
RESEARCH_CONTENT_MIN_LENGTH_DEEP = 200      # Direct HTTP GET (deep mode, higher bar)

# Per-source content limit passed to the LLM (chars, applied per URL's content)
RESEARCH_CONTENT_CHUNK_LIMIT = 15000

# =============================================================================
# RAG & EMBEDDINGS
# =============================================================================
try:
    from backend.models import get_embedding_model
    EMBEDDING_MODEL = get_embedding_model()
    if not isinstance(EMBEDDING_MODEL, str):
        EMBEDDING_MODEL = "embeddinggemma/embeddinggemma-300M-Q8_0"
except Exception:
    EMBEDDING_MODEL = "embeddinggemma/embeddinggemma-300M-Q8_0"

RAG_MIN_SEMANTIC_SCORE = 0.40      # Minimum cosine similarity for retrieval (post-RRF)
RAG_FETCH_MULTIPLIER = 2           # Overfetch ratio for re-ranking
RAG_GRID_WORKERS = int(os.getenv("RAG_GRID_WORKERS", 16))  # Parallel workers for optimization

# =============================================================================
# EMBEDDING TOKEN LIMITS
# Maximum tokens per embedding request (to stay within tokenizer context window)
# Using 1000 tokens per chunk: embeddinggemma-300m has 2048 context window,
# allowing ~2 chunks per LLM context window for retrieval with better context
# =============================================================================
EMBEDDING_MAX_TOKENS_PREFERENCES = int(os.getenv("EMBEDDING_MAX_TOKENS_PREFERENCES", 1000))       # User preferences embeddings
EMBEDDING_MAX_TOKENS_RESEARCH = int(os.getenv("EMBEDDING_MAX_TOKENS_RESEARCH", 1000))  # Research RAG embeddings
EMBEDDING_MAX_TOKENS_FILE = int(os.getenv("EMBEDDING_MAX_TOKENS_FILE", 1000))       # File RAG embeddings
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", 64))               # Number of chunks per request

# =============================================================================
# FILE RAG ENHANCEMENTS
# =============================================================================
FILE_CONTENT_TRUNCATION_LIMIT = int(os.getenv("FILE_CONTENT_TRUNCATION_LIMIT", 15000)) # Limit for full file fallback
HYBRID_SEARCH_ENABLED = True          # Enable BM25 + vector fusion for File RAG
CODE_CHUNKING_ENABLED = True          # Enable syntax-aware chunking for code files

# =============================================================================
# FILE TYPE CLASSIFIER
# =============================================================================
FILE_TYPE_DETECTION_ENABLED = True    # Enable content-based file type detection
CLASSIFIER_CODE_THRESHOLD = float(os.getenv("CLASSIFIER_CODE_THRESHOLD", 20.0))
CLASSIFIER_DOC_THRESHOLD = float(os.getenv("CLASSIFIER_DOC_THRESHOLD", 0.35))

# =============================================================================
# USER PREFERENCES MANAGEMENT
# =============================================================================
PREFERENCES_INJECTION_LIMIT = int(os.getenv("PREFERENCES_INJECTION_LIMIT", 20))

# =============================================================================
# RESEARCH: LLM MAX TOKENS
# =============================================================================
RESEARCH_MAX_TOKENS_SCOUT = int(os.getenv("RESEARCH_MAX_TOKENS_SCOUT", 8192))
RESEARCH_MAX_TOKENS_PLANNING = int(os.getenv("RESEARCH_MAX_TOKENS_PLANNING", 8192))
RESEARCH_MAX_TOKENS_REFLECTION = int(os.getenv("RESEARCH_MAX_TOKENS_REFLECTION", 8192))
RESEARCH_MAX_TOKENS_STEP_WRITER = int(os.getenv("RESEARCH_MAX_TOKENS_STEP_WRITER", 16384))
RESEARCH_MAX_TOKENS_SUMMARY = int(os.getenv("RESEARCH_MAX_TOKENS_SUMMARY", 8192))
RESEARCH_MAX_TOKENS_SYNTHESIS = int(os.getenv("RESEARCH_MAX_TOKENS_SYNTHESIS", 16384))
RESEARCH_MAX_TOKENS_TRIAGE = int(os.getenv("RESEARCH_MAX_TOKENS_TRIAGE", 16384))
RESEARCH_MAX_TOKENS_AUDIT = int(os.getenv("RESEARCH_MAX_TOKENS_AUDIT", 8192))

# =============================================================================
# RESEARCH: SECTION-BASED PLANNING & EXECUTION
# =============================================================================
RESEARCH_MAX_RETRIES = int(os.getenv("RESEARCH_MAX_RETRIES", 3))        # General research retry limit
RESEARCH_SEARCH_RETRIES = int(os.getenv("RESEARCH_SEARCH_RETRIES", 2))  # Retry full search set N times before failing
RESEARCH_MAX_PLAN_RETRIES = 3              # Planner retries on validation failure
RESEARCH_SCOUT_MAX_TURNS = 10              # Prevent infinite context gathering
RESEARCH_MAX_SECTION_STALLS = 3            # Max times a section can retry before skipping
RESEARCH_MAX_AUDITOR_TURNS = 15            # Hard limit on Auditor tool-calling loop
RESEARCH_MAX_SYNTHESIS_TURNS = 15          # Hard limit on Synthesis tool-calling loop
RESEARCH_MAX_QUERIES_PER_SECTION = 2       # Max search queries per report section
RESEARCH_MAX_TOTAL_QUERIES = 10            # Cap across all sections in a plan
RESEARCH_MAX_GAPS_PER_SECTION = int(os.getenv("RESEARCH_MAX_GAPS_PER_SECTION", 2))
RESEARCH_TRIAGE_MAX_FACTS = int(os.getenv("RESEARCH_TRIAGE_MAX_FACTS", 25))
RESEARCH_MIN_SECTION_LEN = 300             # Min chars for a written section to be accepted

# Per-query content budget (actual token counting via token_counter.py)
RESEARCH_CONTENT_BUDGET_REGULAR = 50000    # Tokens per query, regular mode
RESEARCH_CONTENT_BUDGET_DEEP = 80000       # Tokens per query, deep mode

# =============================================================================
# RESEARCH: THINKING BUDGETS (Reasoning Limits)
# Limits on <think> block length (TOKENS) for the llama.cpp thinking_budget_tokens parameter.
# These values ensure the model has enough reasoning space for each phase.
# =============================================================================
RESEARCH_THINKING_BUDGET_SCOUT_TOKENS = 1500
RESEARCH_THINKING_BUDGET_PLANNING_TOKENS = 2500
RESEARCH_THINKING_BUDGET_REFLECTION_TOKENS = 2500
RESEARCH_THINKING_BUDGET_TRIAGE_TOKENS = 2500
RESEARCH_THINKING_BUDGET_STEP_WRITER_TOKENS = 5000
RESEARCH_THINKING_BUDGET_SUMMARY_TOKENS = 1500
RESEARCH_THINKING_BUDGET_AUDIT_TOKENS = 4000
RESEARCH_THINKING_BUDGET_VISION_TOKENS = 1000

# =============================================================================
# RESEARCH: SEARCH & SOURCE SELECTION
# =============================================================================
RESEARCH_TAVILY_MAX_RESULTS_INITIAL = int(os.getenv("RESEARCH_TAVILY_MAX_RESULTS_INITIAL", 20))
RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP = int(os.getenv("RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP", 10))
RESEARCH_SELECT_TOP_URLS_COUNT = int(os.getenv("RESEARCH_SELECT_TOP_URLS_COUNT", 4))
RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT = int(os.getenv("RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT", 2))
RESEARCH_SCOUT_PRELIM_RESULTS_COUNT = 5    # Scout phase preliminary search count
RESEARCH_DEEP_MAP_MAX_URLS = 5             # Max sub-pages to crawl per source (deep mode)
TAVILY_MAP_MAX_DEPTH = 3                   # Crawl depth for Tavily Map
TAVILY_MAP_MAX_BREADTH = 10                # Crawl breadth for Tavily Map

# =============================================================================
# RESEARCH: FINAL AUDIT & REFINEMENT
# =============================================================================
RESEARCH_AUDIT_ENABLED = True
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999     # Fix all citation/contradiction issues
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5     # Cap rewrites for medium issues
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3        # Cap rewrites for low issues
RESEARCH_SURGEON_MAX_RETRIES = 2           # Max attempts per section before structured fallback

# =============================================================================
# RESEARCH: VISION & IMAGE PROCESSING
# =============================================================================
RESEARCH_MAX_IMAGES_PER_PAGE = 3           # Max inline images to VLM-process per page
RESEARCH_MAX_SEARCH_IMAGES = 10            # Max Tavily search result images to process
RESEARCH_VISION_RETRIES = 3                # Retries for VLM inference calls

# =============================================================================
# LOCALIZATION & TIME
# =============================================================================
USER_TIMEZONE = os.getenv("TZ", "Asia/Kolkata")

# =============================================================================
# FILE_SYSTEM SYSTEM
# =============================================================================
# Max characters of file_system content injected into the system prompt as active
# file_system context. Large research reports easily exceed 20k chars; 32k covers
# most reports while keeping the system prompt manageable.
FILE_SYSTEM_ACTIVE_CONTEXT_CHAR_LIMIT = 32000

# =============================================================================
# CACHE TTL CONFIGURATION
# =============================================================================
CACHE_ENTRY_TTL_SECONDS = int(os.getenv("CACHE_ENTRY_TTL_SECONDS", 3600))      # 1 hour default
CACHE_CLEANUP_INTERVAL = int(os.getenv("CACHE_CLEANUP_INTERVAL", 300))         # 5 min
CACHE_RETRY_COUNT = int(os.getenv("CACHE_RETRY_COUNT", 2))                     # Retry attempts

# =============================================================================
# ERROR HANDLING CONFIGURATION
# =============================================================================
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", 5))     # Failures before opening circuit
CIRCUIT_RECOVERY_TIMEOUT = float(os.getenv("CIRCUIT_RECOVERY_TIMEOUT", 30))    # Seconds before attempting recovery

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================
RETRY_COUNT = int(os.getenv("RETRY_COUNT", 2))

# LLM-specific retries (for reasoning-only or malformed tool calls)
LLM_RETRY_COUNT = int(os.getenv("LLM_RETRY_COUNT", 3))
LLM_RETRY_DELAY = float(os.getenv("LLM_RETRY_DELAY", 0.5))

# =============================================================================
# VALIDATION CONFIGURATION (TEMPORARY FOR FRONTEND OVERHAUL)
# =============================================================================
# TEMPORARY: Disable output validation during frontend overhaul
# The new storage model stores SSE artifacts separately, so validation
# that expects inline tags will fail. Re-enable after builder is implemented.
VALIDATION_ENABLED = False

# =============================================================================
# TOOL CONFIGURATION
# =============================================================================
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", 100))
MAX_TOOL_CALLS_BUFFER = int(os.getenv("MAX_TOOL_CALLS_BUFFER", 5))

# =============================================================================
# FILE UPLOAD SETTINGS
# =============================================================================
# Maximum file size for uploads (default 100MB for text-only models)
FILE_UPLOAD_MAX_SIZE = int(os.getenv("FILE_UPLOAD_MAX_SIZE", 100 * 1024 * 1024))  # 100MB
FILE_STORAGE_PATH = os.path.join(DATA_DIR, 'files')
os.makedirs(FILE_STORAGE_PATH, exist_ok=True)

from backend.file_types import EXHAUSTIVE_TEXT_EXTENSIONS

# Base MIME types for documents and media
_BASE_ALLOWED_TYPES = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/heic',
    'video/mp4',
    'video/webm',
    'audio/mpeg',
    'audio/wav'
]

# Dynamically combine base types with all exhaustive text/code extensions
FILE_UPLOAD_ALLOWED_TYPES = list(set(_BASE_ALLOWED_TYPES + list(EXHAUSTIVE_TEXT_EXTENSIONS.values())))

# File processing options
# FILE_RAG_ENABLED: Enable RAG storage for uploaded files
# FILE_VISION_ENABLED: Enable vision processing for image/video files
# For text-only models: RAG enabled, vision disabled
FILE_RAG_ENABLED = True
FILE_VISION_ENABLED = True  # Maximum tool rounds per conversation

# Text-only model file upload settings
# TEXT_ONLY_MODEL_MAX_FILES: Maximum number of files per chat for text-only models
# Set to None for no limit, or a positive integer to enforce a limit
TEXT_ONLY_MODEL_MAX_FILES = None  # No limit by default

# =============================================================================
# FILE UPLOAD - ADDITIONAL SETTINGS
# =============================================================================
# Maximum pages to extract from PDF for vision analysis
PDF_PAGE_LIMIT = int(os.getenv("PDF_PAGE_LIMIT", 5))

# =============================================================================
# PDF EXTRACTION SETTINGS
# =============================================================================
# Enable PDF text extraction
PDF_EXTRACTOR_ENABLED = True
# Enable OCR fallback for scanned PDFs
PDF_OCR_ENABLED = True
# OCR languages to use (easyocr supported languages)
PDF_OCR_LANGUAGES = ['en']
# Minimum content length required after extraction
PDF_EXTRACTION_MIN_CONTENT = 50

# =============================================================================
# DOCUMENT AGENT CONFIGURATION
# =============================================================================
DOCUMENT_AGENT_MAX_TURNS = int(os.getenv("DOCUMENT_AGENT_MAX_TURNS", 100))
DOCUMENT_AGENT_FAILSAFE_TURNS = int(os.getenv("DOCUMENT_AGENT_FAILSAFE_TURNS", 5))
DOCUMENT_AGENT_MAX_LINES_PER_REQUEST = int(os.getenv("DOCUMENT_AGENT_MAX_LINES_PER_REQUEST", 100)) # Rejection limit for reading too many lines
DOCUMENT_AGENT_MAX_CHARS_PER_READ = int(os.getenv("DOCUMENT_AGENT_MAX_CHARS_PER_READ", 15000)) # Safety cap for token context per read
DOCUMENT_AGENT_RAG_DEPTH_MAP = {"basic": 3, "standard": 5, "deep": 7}

# =============================================================================
# FILE_SYSTEM EDITOR CONFIGURATION
# =============================================================================
FILE_SYSTEM_MAX_SEARCH_RESULTS = int(os.getenv("FILE_SYSTEM_MAX_SEARCH_RESULTS", 15))
FILE_SYSTEM_SEARCH_CONTEXT_LINES = int(os.getenv("FILE_SYSTEM_SEARCH_CONTEXT_LINES", 2))
# Content search route (GET /api/file_systems/search)
FILE_SEARCH_DEFAULT_RESULTS = int(os.getenv("FILE_SEARCH_DEFAULT_RESULTS", 50))
FILE_SEARCH_MAX_RESULTS = int(os.getenv("FILE_SEARCH_MAX_RESULTS", 200))
FILE_SEARCH_MAX_QUERY_CHARS = int(os.getenv("FILE_SEARCH_MAX_QUERY_CHARS", 200))
FILE_SEARCH_MAX_LINE_CHARS = int(os.getenv("FILE_SEARCH_MAX_LINE_CHARS", 300))
MAX_FS_AGENT_INSTRUCTION_LENGTH = int(os.getenv("MAX_FS_AGENT_INSTRUCTION_LENGTH", 2000))
FILE_SYSTEM_AGENT_MAX_TURNS = int(os.getenv("FILE_SYSTEM_AGENT_MAX_TURNS", 100))
FILE_SYSTEM_AGENT_FAILSAFE_TURNS = int(os.getenv("FILE_SYSTEM_AGENT_FAILSAFE_TURNS", 10))

# =============================================================================
# BROWSING AGENT CONFIGURATION
# =============================================================================
BROWSING_AGENT_MAX_TURNS = int(os.getenv("BROWSING_AGENT_MAX_TURNS", 100))
BROWSING_AGENT_FAILSAFE_TURNS = int(os.getenv("BROWSING_AGENT_FAILSAFE_TURNS", 10))
BROWSING_AGENT_MAX_CHARS_PER_PAGE = int(os.getenv("BROWSING_AGENT_MAX_CHARS_PER_PAGE", 20000))
BROWSING_AGENT_MAX_CHARS_INTERACTIVE = int(os.getenv("BROWSING_AGENT_MAX_CHARS_INTERACTIVE", 15000))
BROWSER_STEALTH_LEVEL = os.getenv("BROWSER_STEALTH_LEVEL", "minimal")  # minimal, advanced

# =============================================================================
# AGENT MAX OUTPUT TOKENS CONFIGURATION
# =============================================================================
SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT = int(os.getenv("SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT", 40000))
SEARCH_WEB_AGENT_MAX_TOKENS = int(os.getenv("SEARCH_WEB_AGENT_MAX_TOKENS", 16384))
DOCUMENT_AGENT_MAX_TOKENS = int(os.getenv("DOCUMENT_AGENT_MAX_TOKENS", 16384))
FILE_SYSTEM_AGENT_MAX_TOKENS = int(os.getenv("FILE_SYSTEM_AGENT_MAX_TOKENS", 16384))
BROWSING_AGENT_MAX_TOKENS = int(os.getenv("BROWSING_AGENT_MAX_TOKENS", 16384))
VISIT_PAGE_AGENT_MAX_TOKENS = int(os.getenv("VISIT_PAGE_AGENT_MAX_TOKENS", 16384))

SEARCH_WEB_AGENT_THINKING_BUDGET = int(os.getenv("SEARCH_WEB_AGENT_THINKING_BUDGET", 1024))
DOCUMENT_AGENT_THINKING_BUDGET = int(os.getenv("DOCUMENT_AGENT_THINKING_BUDGET", 1024))
FILE_SYSTEM_AGENT_THINKING_BUDGET = int(os.getenv("FILE_SYSTEM_AGENT_THINKING_BUDGET", 1024))
BROWSING_AGENT_THINKING_BUDGET = int(os.getenv("BROWSING_AGENT_THINKING_BUDGET", 1024))
VISIT_PAGE_AGENT_THINKING_BUDGET = int(os.getenv("VISIT_PAGE_AGENT_THINKING_BUDGET", 1024))

# =============================================================================
# AGENT SAFETY & PROGRESS MONITORING
# =============================================================================
AGENT_SAFETY_ERROR_LOOP_THRESHOLD = int(os.getenv("AGENT_SAFETY_ERROR_LOOP_THRESHOLD", 2))
AGENT_SAFETY_TOOL_LOOP_THRESHOLD = int(os.getenv("AGENT_SAFETY_TOOL_LOOP_THRESHOLD", 3))
AGENT_SAFETY_STAGNATION_THRESHOLD = int(os.getenv("AGENT_SAFETY_STAGNATION_THRESHOLD", 3))

# =============================================================================
# GIT AGENT CONFIGURATION
# =============================================================================
GIT_AGENT_MAX_TURNS = int(os.getenv("GIT_AGENT_MAX_TURNS", 50))
GIT_AGENT_FAILSAFE_TURNS = int(os.getenv("GIT_AGENT_FAILSAFE_TURNS", 5))
GIT_AGENT_MAX_TOKENS = int(os.getenv("GIT_AGENT_MAX_TOKENS", 8192))
GIT_AGENT_THINKING_BUDGET = int(os.getenv("GIT_AGENT_THINKING_BUDGET", 1024))
GIT_COMMAND_TIMEOUT = int(os.getenv("GIT_COMMAND_TIMEOUT", 120))  # seconds

# Default allowed git subcommands (read-only + clone enabled by default)
# These defaults are used when no system_settings DB override exists.
GIT_DEFAULT_ALLOWED_COMMANDS = [
    "clone", "status", "log", "diff", "show"
]

# Permanently blocked commands — these are NEVER allowed regardless of settings
# (Currently empty — all commands including push are configurable)
GIT_PERMANENTLY_BLOCKED_COMMANDS: list = []

# All known git subcommands available for the settings UI
GIT_ALL_KNOWN_COMMANDS = [
    # Read-only (enabled by default)
    "clone", "status", "log", "diff", "show",
    # Modifying (disabled by default, can be enabled)
    "init", "add", "rm", "commit",
    "branch", "checkout", "switch",
    "fetch", "pull", "merge",
    "stash", "tag", "remote", "config",
    "reset", "rebase", "clean",
    # Remote-write (disabled by default, can be enabled)
    "push",
]


# =============================================================================
# CODE RUNNER CONFIGURATION
# =============================================================================
CODE_RUNNER_URL = os.getenv("CODE_RUNNER_URL", "http://code_runner_mcp:8100")
CODE_RUNNER_API_KEY = get_secret("CODE_RUNNER_API_KEY")
CODE_RUNNER_DEFAULT_TIMEOUT = int(os.getenv("CODE_RUNNER_DEFAULT_TIMEOUT", "30"))
# Keep this at or below the runtime ceiling MAX_TIMEOUT in code_runner_mcp/server.py (it clamps silently above it).
CODE_RUNNER_MAX_TIMEOUT = int(os.getenv("CODE_RUNNER_MAX_TIMEOUT", "120"))
CODE_RUNNER_MAX_OUTPUT_SIZE = int(os.getenv("CODE_RUNNER_MAX_OUTPUT_SIZE", "65536"))  # 64KB
# Code runs are serialised process-wide (backend/tools/implementations/run_slot.py): a user may hold this many places
# (the running run plus queued ones), and a run waits at most this many seconds for the slot.
# Clamped to at least 1 place and a non-negative wait, so a bad value cannot refuse every run.
CODE_RUNNER_MAX_QUEUED_PER_USER = max(1, int(os.getenv("CODE_RUNNER_MAX_QUEUED_PER_USER", "2")))
CODE_RUNNER_QUEUE_TIMEOUT = max(0, int(os.getenv("CODE_RUNNER_QUEUE_TIMEOUT", "120")))
CODE_RUNNER_MEMORY_LIMIT = os.getenv("CODE_RUNNER_MEMORY_LIMIT", "512M")
CODE_RUNNER_CPU_LIMIT = os.getenv("CODE_RUNNER_CPU_LIMIT", "1.0")

# Extension → language mapping for run_file
CODE_EXTENSION_MAP = {
    ".py": "python", ".c": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".java": "java", ".js": "javascript", ".mjs": "javascript",
    ".ts": "typescript", ".go": "go", ".rs": "rust",
    ".sh": "bash", ".bash": "bash", ".php": "php", ".sql": "sql",
}


