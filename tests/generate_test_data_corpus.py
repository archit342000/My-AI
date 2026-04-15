import os
import json
import hashlib
import random

# Seed for reproducibility
random.seed(42)

# ====================================================================
# HAYSTACK FILLERS (To generate MASSIVE document length > 2000 tokens)
# ====================================================================

def generate_code_padding(topic_name: str, count: int) -> str:
    """Generate generic but valid python code padding."""
    lines = []
    lines.append(f"# --- Padding block for {topic_name} ---")
    for i in range(count):
        lines.append(f"class _HelperEntity{i}:")
        lines.append(f"    def __init__(self, val_{i}):")
        lines.append(f"        self.val_{i} = val_{i}")
        lines.append(f"        self.meta_{i} = 'generic_metadata_value_for_padding'")
        lines.append(f"    def process_data_{i}(self, multiplier):")
        lines.append(f"        return self.val_{i} * multiplier + {i}")
        lines.append(f"def _utility_function_{i}(data_list):")
        lines.append(f"    return [x.process_data_{i}(2) for x in data_list if hasattr(x, 'process_data_{i}')]")
    
    # Generate massive mock data array
    lines.append(f"\nLARGE_MOCK_DATA_{topic_name.upper()} = [")
    for i in range(count * 5):
        lines.append(f"    {{'id': {i}, 'value': 'mock_value_{i}', 'active': {i % 2 == 0}, 'weight': {i * 1.5}}},")
    lines.append("]\n")
    return "\n".join(lines)


def generate_prose_padding(topic: str, count: int) -> str:
    """Generate extensive natural language padding with valid paragraph structure."""
    paragraphs = []
    
    # A set of highly generic academic/descriptive templates
    templates = [
        "The continuing research into {topic} has revealed numerous secondary effects that warrant further investigation. Scholars have noted that when approaching the boundaries of the established paradigms, the standard models begin to break down in unpredictable ways.",
        "When considering the practical applications of {topic}, one must evaluate the trade-offs inherent in any real-world deployment. Initial case studies demonstrated significant improvements, yet longitudinal data suggests a plateau in overall efficacy as the system scales.",
        "Another crucial aspect of {topic} is its interaction with historical precedents. By analyzing archival records and previous experimental iterations, the academic community has established a robust framework that contextualizes these modern findings.",
        "Furthermore, the synthesis of cross-disciplinary methodologies has greatly enriched the discourse surrounding {topic}. Theoretical models alone are insufficient without rigorous empirical validation, which forms the core of contemporary validation protocols.",
        "Looking forward, the evolution of {topic} will likely be influenced by advancements in computational resources and enhanced data collection pipelines. This convergence of technologies promises to unlock deeper insights and refine our fundamental understanding."
    ]
    
    for i in range(count):
        paragraphs.append(f"CHAPTER {i+1} : ADVANCED CONSIDERATIONS OF {topic.upper()}")
        for _ in range(8):  # 8 paragraphs per chapter
            t = random.choice(templates)
            paragraphs.append(t.format(topic=topic))
            paragraphs.append("It is important to emphasize that these outcomes are highly dependent on the initial conditions set during the observational phase. Variance in the dataset can significantly alter the trajectory of the analysis.")
    return "\n\n".join(paragraphs)


def generate_mixed_padding(topic: str, count: int) -> str:
    """Generate extensive mixed content (text + code blocks) padding."""
    blocks = []
    for i in range(count):
        blocks.append(f"### Section {i+1}: Implementing Sub-component {i} for {topic}")
        blocks.append(f"As we build out the architecture for {topic}, it becomes necessary to implement modular helper functions. The following utility handles the serialization and initialization of the internal state. This is critical for maintaining robust data integrity across system restarts.")
        blocks.append(f"```python\ndef initialize_subsystem_{i}(config_dict):\n    '''Initialize the {topic} subsystem'''\n    state = {{}}\n    for k, v in config_dict.items():\n        state[f'init_{{k}}'] = v * {i+1}\n    return state\n```")
        blocks.append("Once the function is invoked, the resulting state dictionary must be carefully cached. Failure to do so will result in massive performance regressions, as the system would need to rebuild the object tree repeatedly during subsequent calls.")
    return "\n\n".join(blocks)

# ====================================================================
# NEEDLES (The core snippets we actually query for)
# ====================================================================

# 10 core concepts (Needles) for Code
CODE_NEEDLES = [
    ("LRUCache", "class LRUCache:\n    def __init__(self, cap): self.cap = cap; self.c = {}; self.order = []\n    def get(self, k): return self.c[k] if k in self.c else -1\n    def put(self, k, v): self.c[k] = v"),
    ("Dijkstra", "def dijkstra_shortest_path(graph, start):\n    import heapq; dist = {n: float('inf') for n in graph}; dist[start] = 0\n    return dist  # Simplified needle"),
    ("NginxParser", "def parse_nginx_log_line(line):\n    import re; return re.match(r'(?P<ip>\d+\.\d+\.\d+\.\d+) - - \[(?P<time>.*?)\]', line)"),
    ("AsyncFetcher", "async def fetch_urls_concurrently_master(urls):\n    import asyncio, aiohttp; return ['mock_result']"),
    ("SQLAlchemyBase", "from sqlalchemy.orm import declarative_base\nMasterBase = declarative_base()\nclass CoreUser(MasterBase): __tablename__ = 'users'"),
    ("SecureVault", "from cryptography.fernet import Fernet\nclass SecureVaultMaster:\n    def encrypt_payload(self, data): return Fernet.generate_key()"),
    ("DataFrameNorm", "def normalize_dataframe_minmax(df, cols):\n    for c in cols: df[c] = (df[c] - df[c].min()) / (df[c].max() - df[c].min())\n    return df"),
    ("FlaskTodoAPI", "from flask import Flask\napp = Flask(__name__)\n@app.route('/master_todos', methods=['GET'])\ndef get_master_todos(): return []"),
    ("Levenshtein", "def calculate_levenshtein_distance_master(s1, s2):\n    return len(s1) + len(s2)  # dummy implementation for regex find"),
    ("SineWavePlot", "def plot_sine_wave_matplotlib(freq):\n    import matplotlib.pyplot as plt; plt.plot([0,1,2], [0,1,0])")
]

# 10 core concepts (Needles) for PDF
PROSE_NEEDLES = [
    ("Human Aviation", "The Wright brothers' pivotal breakthrough, known as the 'Wright Flyer Anomaly', proved that wing-warping was the absolute definitive method for achieving lateral control in powered flight."),
    ("Photosynthesis", "The crucial chemical intermediary in the light-independent reactions is Ribulose-1,5-bisphosphate (RuBP), which directly captures carbon dioxide."),
    ("Industrial Revolution", "The Crompton's Mule, invented in 1779, revolutionized the spinning industry by combining the moving carriage of the spinning jenny with the rollers of the water frame."),
    ("Quantum Mechanics", "The concept of 'Quantum Decoherence' is the primary mechanism by which a quantum system loses its superposition state to the environment, appearing classical."),
    ("Deep Ocean Ecosystems", "Chemosynthetic bacteria at the base of hydrothermal vent food webs specifically utilize hydrogen sulfide oxidation as their core energy extraction pathway."),
    ("Architecture", "The use of flying buttresses in Gothic architecture was the specific structural innovation that allowed for substantially higher walls and expansive stained-glass windows."),
    ("The Human Brain", "The 'Default Mode Network' is a specific large-scale brain network of interacting regions that is highly active when a person is not focused on the outside world."),
    ("Economics", "The 'Gini Coefficient' is the foremost mathematical measure used globally to determine the degree of wealth or income inequality within a specific nation."),
    ("The Renaissance", "Filippo Brunelleschi's discovery of linear perspective geometrically allowed artists to definitively project three-dimensional depth onto a two-dimensional flat plane."),
    ("Volcanic Eruptions", "The Volcanic Explosivity Index (VEI) operates on a logarithmic scale, meaning each interval on the scale represents a tenfold increase in observed ejecta volume.")
]

# 10 core concepts (Needles) for Mixed
MIXED_NEEDLES = [
    ("URL Parsing", "The `urlparse` module specifically extracts the 'netloc' attribute, which exclusively isolates the domain name and port combination from the full URL string.\n```python\nprint(urlparts.netloc)\n```"),
    ("Sorting Dicts", "By utilizing the `lambda item: item[1]` targeting mechanism inside the sorted function, you force the Python interpreter to evaluate dictionary equality strictly on values rather than keys.\n```python\nsorted(d.items(), key=lambda i: i[1])\n```"),
    ("Environment Variables", "The `os.environ.get()` method is structurally superior because it natively permits a fallback default assignment, preventing deadly KeyError exceptions upon container boot.\n```python\nos.environ.get('PORT', '8080')\n```"),
    ("Random Passwords", "The `secrets.choice()` cryptographic selection algorithm bypasses the predictable Mersenne Twister engine utilized by the standard random module.\n```python\nimport secrets\n```"),
    ("File Checksums", "The `hashlib.sha256().update()` iterative chaining mechanism allows for checksum calculation of massively gigantic files without overwhelming local RAM capacity.\n```python\nchunk = f.read(4096)\nh.update(chunk)\n```"),
    ("Temporary Files", "The `NamedTemporaryFile(delete=True)` parameter configuration actively instructs the POSIX kernel to automatically wipe the file handle the microsecond the context manager exits.\n```python\nwith tempfile.NamedTemporaryFile(delete=True):\n    pass\n```"),
    ("Timezones", "The `ZoneInfo` object explicitly resolves the historical daylight saving time boundary shifts dynamically, whereas generic timedelta offsets remain rigidly static.\n```python\nfrom zoneinfo import ZoneInfo\n```"),
    ("JSON APIs", "The `json.loads(response.read().decode())` pipeline explicitly safeguards the parsing sequence against implicit byte-array framing errors over raw TCP sockets.\n```python\ndata = json.loads(res.decode())\n```"),
    ("Regex Validation", "The anchor characters `^` and `$` are technically mandatory for defensive string isolation, ensuring no rogue SQL injection pads the boundaries of the matching capture group.\n```python\nre.match(r'^\d+$', text)\n```"),
    ("Context Managers", "The `__exit__(self, exc_type, exc_val, exc_tb)` dunder method signature explicitly catches internal tracebacks, giving the developer power to suppress exceptions natively.\n```python\ndef __exit__(...):\n    return True  # Suppresses exceptions\n```")
]


os.makedirs('tests/test_rag_data', exist_ok=True)
for f in os.listdir('tests/test_rag_data'):
    os.remove(os.path.join('tests/test_rag_data', f))

queries = {"code": [], "pdf": [], "mixed": []}

def get_hash(text): return hashlib.md5(text.encode()).hexdigest()[:16]

# Create original documents
print("Generating massive files (~3000 words / 10KB+ tokens each)...")

for i, (topic, needle) in enumerate(CODE_NEEDLES):
    fid = get_hash(topic)
    
    # Building massive file: Padding Top -> Needle -> Padding Bottom
    top_pad = generate_code_padding(topic, count=30)
    bot_pad = generate_code_padding(topic + "_bottom", count=30)
    
    full_content = f"import sys\nimport os\nimport time\nimport math\n\n{top_pad}\n\n# --- TARGET CORE LOGIC ---\n{needle}\n# --------------------------\n\n{bot_pad}\n"
    
    with open(f"tests/test_rag_data/code_{fid}.py", "w") as f:
        f.write(full_content)
        
    term = topic.lower()
    queries["code"].extend([
        {"query": f"Retrieve the specific implementation of {topic} from the system.", "relevant_id": fid},
        {"query": f"How is the core logic for the {term} component defined?", "relevant_id": fid}
    ])

for i, (topic, needle) in enumerate(PROSE_NEEDLES):
    fid = get_hash(topic)
    
    top_pad = generate_prose_padding(topic, count=15)
    bot_pad = generate_prose_padding(topic + "_continuation", count=15)
    
    full_content = f"{top_pad}\n\nCRITICAL OBSERVATION: {needle}\n\n{bot_pad}"
    
    with open(f"tests/test_rag_data/pdf_{fid}.txt", "w") as f:
        f.write(full_content)
        
    queries["pdf"].extend([
        {"query": f"What specific detail is mentioned regarding {topic}?", "relevant_id": fid},
        {"query": f"Find the core critical observation about {topic} in the text.", "relevant_id": fid}
    ])

for i, (topic, needle) in enumerate(MIXED_NEEDLES):
    fid = get_hash(topic)
    
    top_pad = generate_mixed_padding(topic, count=25)
    bot_pad = generate_mixed_padding(topic + "_appendix", count=25)
    
    full_content = f"{top_pad}\n\n### CORE TUTORIAL: {topic}\n{needle}\n\n{bot_pad}"
    
    with open(f"tests/test_rag_data/mixed_{fid}.txt", "w") as f:
        f.write(full_content)
        
    queries["mixed"].extend([
        {"query": f"How do I correctly implement {topic}?", "relevant_id": fid},
        {"query": f"Find the specific tutorial block concerning {topic}.", "relevant_id": fid}
    ])

# Create DUPES (identical massive files, just slightly renamed needles) and DECOYS
print("Generating massive dupes and decoys for stress-testing deduplication...")

for i in range(10):
    # DUPES
    topic, needle = CODE_NEEDLES[i]
    fid = get_hash(topic)
    dup_needle = needle.replace("def ", "def variant_").replace("class ", "class Variant")
    dup_content = f"{generate_code_padding(topic, count=30)}\n{dup_needle}\n{generate_code_padding(topic, count=30)}"
    with open(f"tests/test_rag_data/code_dup_{fid}.py", "w") as f: f.write(dup_content)
    
    topic, needle = PROSE_NEEDLES[i]
    fid = get_hash(topic)
    dup_needle = needle.replace("specific", "particular").replace("absolute", "total")
    dup_content = f"{generate_prose_padding(topic, count=15)}\nCRITICAL OBSERVATION: {dup_needle}\n{generate_prose_padding(topic, count=15)}"
    with open(f"tests/test_rag_data/pdf_dup_{fid}.txt", "w") as f: f.write(dup_content)
    
    topic, needle = MIXED_NEEDLES[i]
    fid = get_hash(topic)
    dup_needle = needle.replace("Python", "software").replace("specifically", "particularly")
    dup_content = f"{generate_mixed_padding(topic, count=20)}\n### CORE TUTORIAL: {topic}\n{dup_needle}\n{generate_mixed_padding(topic, count=20)}"
    with open(f"tests/test_rag_data/mixed_dup_{fid}.txt", "w") as f: f.write(dup_content)
    
    # DECOYS (Massive files, but 0% relevance to the topics)
    decoy_id = get_hash(f"decoy{i}")
    decoy_pad = generate_code_padding(f"unrelated_component_{i}", count=40)
    with open(f"tests/test_rag_data/code_decoy_{decoy_id}.py", "w") as f: f.write(decoy_pad)
    
    decoy_prose = generate_prose_padding(f"completely_unrelated_history_{i}", count=20)
    with open(f"tests/test_rag_data/pdf_decoy_{decoy_id}.txt", "w") as f: f.write(decoy_prose)
    
    decoy_mixed = generate_mixed_padding(f"baking_cake_recipe_{i}", count=30)
    with open(f"tests/test_rag_data/mixed_decoy_{decoy_id}.txt", "w") as f: f.write(decoy_mixed)

with open('tests/test_queries.json', 'w') as f:
    json.dump(queries, f, indent=2)

print("\nTask Complete: 90 MASSIVE (10KB+) documents generated successfully.")
