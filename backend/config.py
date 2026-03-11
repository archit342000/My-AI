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
# APP LEVEL AUTH
# =============================================================================
APP_PASSWORD = get_secret("APP_PASSWORD", None)

# =============================================================================
# LM STUDIO & INFRASTRUCTURE
# =============================================================================
LM_STUDIO_URL = get_secret("LM_STUDIO_URL", "http://localhost:1234")
LM_STUDIO_API_KEY = get_secret("LM_STUDIO_API_KEY", "")
CHROMA_PATH = get_secret("CHROMA_PATH", os.path.join(DATA_DIR, "chroma_db"))

# =============================================================================
# SEARCH (Tavily API)
# =============================================================================
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "")
TAVILY_BASE_URL = os.getenv("TAVILY_BASE_URL", "https://api.tavily.com")

SEARCH_DEPTH = "basic"
MAX_SEARCH_RESULTS = 5
MIN_SEARCH_RESULTS = 3
INCLUDE_ANSWER = "advanced"
INCLUDE_RAW_CONTENT = True
RELEVANCE_THRESHOLD = 0.6          # Below this, trim results (keep MIN_SEARCH_RESULTS)
SEARCH_CACHE_TTL = 3600            # Seconds before cached search expires

# =============================================================================
# NETWORK & INTEGRATION TIMEOUTS (seconds)
# =============================================================================
TIMEOUT_LLM_BLOCKING = None        # Standard chat completions (None = infinite for local queue)
TIMEOUT_LLM_ASYNC = None           # Parallel AI generation tasks
TIMEOUT_TAVILY_SEARCH = 15         # Sync search
TIMEOUT_TAVILY_SEARCH_ASYNC = 60   # Async search
TIMEOUT_TAVILY_MAP = 150           # Deep link discovery (slow because recursive)
TIMEOUT_TAVILY_EXTRACT = 60        # JS-rendered page scraping fallback
TIMEOUT_WEB_SCRAPE = 15            # Standard HTTP GET for markdown extraction
TIMEOUT_IMAGE_FETCH = 15           # Base64-encoding images for VLM
TIMEOUT_URLHAUS = 5                # URLhaus malware check

# =============================================================================
# WEB EXTRACTION & PARSING
# =============================================================================
URL_FETCH_RETRIES = 5              # Max redirects to follow
MAX_CHARS_VISIT_PAGE = 8000        # Character cap for standard visit_page tool

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
RAG_CHUNK_MAX_CHARS = 2200         # Max chars per embedding chunk
RAG_MIN_SEMANTIC_SCORE = 0.50      # Minimum cosine similarity for retrieval
RAG_DEDUP_THRESHOLD = 0.90         # Similarity above this = duplicate chunk
RAG_FETCH_MULTIPLIER = 5           # Overfetch ratio for re-ranking
RAG_DECAY_RATE = 0.10              # Time-decay weight for older memories
RAG_RETRIEVAL_LIMIT = 500          # Hard cap on total retrieved chunks

# =============================================================================
# UI & STREAMING
# =============================================================================
RESEARCH_UI_THOUGHT_MIN_LENGTH = 15       # Min chars to show reasoning snippet
RESEARCH_UI_THOUGHT_SNIPPET_LENGTH = 120  # Max chars shown in real-time thought preview
RESEARCH_UI_STREAM_UPDATE_INTERVAL = 40   # Characters between stream flush events
RESEARCH_VISION_MIN_RESPONSE_LENGTH = 20  # Min VLM response to consider valid

# =============================================================================
# RESEARCH: LLM MAX TOKENS
# =============================================================================
RESEARCH_MAX_TOKENS_SCOUT = int(os.getenv("RESEARCH_MAX_TOKENS_SCOUT", 8192))
RESEARCH_MAX_TOKENS_PLANNING = int(os.getenv("RESEARCH_MAX_TOKENS_PLANNING", 8192))
RESEARCH_MAX_TOKENS_REFLECTION = int(os.getenv("RESEARCH_MAX_TOKENS_REFLECTION", 8192))
RESEARCH_MAX_TOKENS_STEP_WRITER = int(os.getenv("RESEARCH_MAX_TOKENS_STEP_WRITER", 16384))
RESEARCH_MAX_TOKENS_SUMMARY = int(os.getenv("RESEARCH_MAX_TOKENS_SUMMARY", 4096))
RESEARCH_MAX_TOKENS_SYNTHESIS = int(os.getenv("RESEARCH_MAX_TOKENS_SYNTHESIS", 16384))
RESEARCH_MAX_TOKENS_VISION = int(os.getenv("RESEARCH_MAX_TOKENS_VISION", 2048))
RESEARCH_MAX_TOKENS_RAG_CONTEXT = int(os.getenv("RESEARCH_MAX_TOKENS_RAG_CONTEXT", 30000))

# Audit max tokens = same as step writer (surgeon patches one section at a time)
RESEARCH_MAX_TOKENS_AUDIT = int(os.getenv("RESEARCH_MAX_TOKENS_AUDIT", RESEARCH_MAX_TOKENS_STEP_WRITER))

# =============================================================================
# RESEARCH: SECTION-BASED PLANNING & EXECUTION
# =============================================================================
RESEARCH_MAX_PLAN_RETRIES = 3              # Planner retries on validation failure
RESEARCH_MAX_QUERIES_PER_SECTION = 2       # Max search queries per report section
RESEARCH_MAX_TOTAL_QUERIES = 10            # Cap across all sections in a plan
RESEARCH_MAX_GAPS_PER_SECTION = int(os.getenv("RESEARCH_MAX_GAPS_PER_SECTION", 2))
RESEARCH_MIN_SECTION_LEN = 300             # Min chars for a written section to be accepted

# Per-query content budget (tokens, estimated as chars / 4)
RESEARCH_CONTENT_BUDGET_REGULAR = 50000    # Tokens per query, regular mode
RESEARCH_CONTENT_BUDGET_DEEP = 80000       # Tokens per query, deep mode

# =============================================================================
# RESEARCH: MEANDER DETECTION
# Limits on <think> block length (chars). If reasoning exceeds the limit AND
# content output is below CONTENT_THRESHOLD, the response is considered
# "meandering" and gets retried or truncated.
# =============================================================================
RESEARCH_MEANDER_CONTENT_THRESHOLD = 500

RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT = 6000
RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING = 10000
RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION = 10000
RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER = 20000
RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY = 6000
RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS = 15000

# Audit meander limit = same as step writer (surgeon produces one section)
RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT = RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER

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
# RESEARCH: LLM TEMPERATURE & SAMPLING
# =============================================================================
RESEARCH_TEMPERATURE_SCOUT = float(os.getenv("RESEARCH_TEMPERATURE_SCOUT", 0.1))
RESEARCH_TEMPERATURE_PLANNING = float(os.getenv("RESEARCH_TEMPERATURE_PLANNING", 0.4))
RESEARCH_TEMPERATURE_REFLECTION = float(os.getenv("RESEARCH_TEMPERATURE_REFLECTION", 0.2))
RESEARCH_TEMPERATURE_STEP_WRITER = float(os.getenv("RESEARCH_TEMPERATURE_STEP_WRITER", 0.4))
RESEARCH_TEMPERATURE_SUMMARY = float(os.getenv("RESEARCH_TEMPERATURE_SUMMARY", 0.2))
RESEARCH_TEMPERATURE_VISION = float(os.getenv("RESEARCH_TEMPERATURE_VISION", 0.1))
RESEARCH_TEMPERATURE_SYNTHESIS = float(os.getenv("RESEARCH_TEMPERATURE_SYNTHESIS", 0.4))
RESEARCH_TEMPERATURE_AUDIT = float(os.getenv("RESEARCH_TEMPERATURE_AUDIT", 0.2))
RESEARCH_TOP_P_PLANNING = float(os.getenv("RESEARCH_TOP_P_PLANNING", 0.9))

# =============================================================================
# RESEARCH: FINAL AUDIT & REFINEMENT
# =============================================================================
RESEARCH_AUDIT_ENABLED = True
RESEARCH_AUDIT_MAX_HIGH_SEVERITY = 999     # Fix all citation/contradiction issues
RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY = 5     # Cap rewrites for medium issues
RESEARCH_AUDIT_MAX_LOW_SEVERITY = 3        # Cap rewrites for low issues
RESEARCH_SURGEON_MAX_RETRIES = 2           # Max attempts per section before structured fallback

# Fallback temperature used on retry attempts (reflection, writer, surgeon)
RESEARCH_TEMPERATURE_RETRY_FALLBACK = 0.1

# =============================================================================
# RESEARCH: VISION & IMAGE PROCESSING
# =============================================================================
RESEARCH_MAX_IMAGES_PER_PAGE = 3           # Max inline images to VLM-process per page
RESEARCH_MAX_SEARCH_IMAGES = 10            # Max Tavily search result images to process
RESEARCH_IMAGE_FETCH_RETRIES = 5           # Retries for fetching image bytes
RESEARCH_VISION_RETRIES = 3               # Retries for VLM inference calls

# =============================================================================
# RESEARCH: CONVERSATION HISTORY CONTEXT
# =============================================================================
RESEARCH_CONTEXT_HISTORY_SCOUT = 5         # Messages passed to scout
RESEARCH_CONTEXT_HISTORY_PLANNING = 10     # Messages passed to planner
# =============================================================================
# LOCALIZATION & TIME
# =============================================================================
USER_TIMEZONE = os.getenv("TZ", "Asia/Kolkata")
