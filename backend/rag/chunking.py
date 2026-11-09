"""
Chunking Module - Content-based file type detection and adaptive chunking.

This module provides:
- File type detection based on content analysis (not just extension)
- Syntax-aware chunking for code files
- Row-based chunking for spreadsheet data
- Hybrid chunking for mixed content
"""
import json
import re
from typing import Tuple, List, Dict, Optional
import bisect
from dataclasses import dataclass

@dataclass
class ChunkResult:
    """A chunk of text with positional metadata, produced by chunking functions.

    Metadata is EXCLUSIVE — a chunk is either page-based or line-based, never both:
      - PDF/page-based docs:  page_number is set; line_start/line_end are None.
      - Code/text/CSV:        line_start and line_end are set; page_number is None.
    """
    text: str
    line_start: Optional[int] = None   # 1-indexed, inclusive (line-based docs only)
    line_end: Optional[int] = None     # 1-indexed, inclusive (line-based docs only)
    page_number: Optional[int] = None  # 1-indexed (page-based docs / PDFs only)

def strip_page_markers(text: str) -> Tuple[str, List[Tuple[int, int]]]:
    """
    Strips '--- PAGE_START_N ---' and '--- PAGE_END_N ---' markers from text.
    Builds a page map mapping clean line numbers to page numbers.
    """
    lines = text.split('\n')
    clean_lines = []
    page_map = []
    current_page = None
    
    start_pattern = re.compile(r'^--- PAGE_START_(\d+) ---$')
    end_pattern = re.compile(r'^--- PAGE_END_(\d+) ---$')
    
    for line in lines:
        start_match = start_pattern.match(line.strip())
        if start_match:
            current_page = int(start_match.group(1))
            page_map.append((len(clean_lines) + 1, current_page))
            continue
            
        end_match = end_pattern.match(line.strip())
        if end_match:
            continue
            
        clean_lines.append(line)
        
    return '\n'.join(clean_lines), page_map

def content_to_index_text(content: str) -> str:
    """
    Turns stored file content into the text that is chunked and embedded.

    Uploads are stored as JSON: `{"format": "pages", "pages": [...]}` for PDFs and
    `{"format": "text", "text": "..."}` for everything else. Page JSON becomes
    `--- PAGE_START_N ---` / `--- PAGE_END_N ---` marker blocks (1-indexed, empty pages kept so the
    numbers match `read_file_range`), text JSON becomes its plain text, and any other input is returned
    unchanged. The stored content itself is never modified.

    A user-uploaded JSON file that happens to have a top-level `format` key is stored as is, so it is
    read like a stored wrapper here: a valid payload is unwrapped, an invalid one raises (the callers log
    it and the file is not indexed), the same way `FileManager` reads it.

    Args:
        content: The stored `content_text` of a file.

    Returns:
        The text to chunk.

    Raises:
        ValueError: If the content has a known `format` but an invalid payload.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content
    if not isinstance(data, dict):
        return content
    fmt = data.get("format")
    if fmt == "pages":
        pages = data.get("pages")
        if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
            raise ValueError("pages content must hold a list of strings")
        return "\n".join(f"--- PAGE_START_{n} ---\n{page}\n--- PAGE_END_{n} ---" for n, page in enumerate(pages, 1))
    if fmt == "text":
        text = data.get("text")
        if not isinstance(text, str):
            raise ValueError("text content must hold a string")
        return text
    return content


def resolve_page_number(line_number: int, page_map: List[Tuple[int, int]]) -> Optional[int]:
    """Finds the page number for a given line using the page map."""
    if not page_map:
        return None
    idx = bisect.bisect_right([p[0] for p in page_map], line_number)
    if idx == 0:
        return None
    return page_map[idx - 1][1]


from backend.rag.token_counter import count_tokens, split_text_by_tokens
from backend import config


# =============================================================================
# File Type Detection
# =============================================================================

def detect_file_type(filename: str, content: str) -> Tuple[str, dict]:
    """Detect file type from content analysis.

    Detection Priority:
    1. Spreadsheet - CSV patterns (consistent comma-separated columns)
    2. Code - Programming language syntax patterns
    3. Document - Natural language patterns
    4. Mixed - Both code and document patterns found

    Args:
        filename: Original filename (used for extension hint)
        content: File content to analyze

    Returns:
        Tuple of (file_type, metadata_dict)
        - file_type: 'spreadsheet', 'code', 'document', 'mixed', 'unknown'
        - metadata_dict: detected properties
    """
    if not content or len(content.strip()) < 10:
        return 'unknown', {}

    # 1. Check for spreadsheet patterns (high confidence)
    if _is_spreadsheet_pattern(content):
        return 'spreadsheet', _analyze_spreadsheet(content)

    # 2. Check for code patterns
    code_score, code_info = _analyze_code_content(content)

    # 3. Check for document patterns
    doc_score = _analyze_document_content(content)

    # 4. Determine final type based on scores (Optimized via Grid Search)
    CODE_THRESHOLD = config.CLASSIFIER_CODE_THRESHOLD
    DOC_THRESHOLD = config.CLASSIFIER_DOC_THRESHOLD

    # Calculate confidence level
    code_confidence = min(code_score / CODE_THRESHOLD, 1.0)
    doc_confidence = min(doc_score / DOC_THRESHOLD, 1.0)

    if code_score >= CODE_THRESHOLD and doc_score >= DOC_THRESHOLD:
        return 'mixed', {'code_info': code_info, 'doc_score': doc_score,
                        'code_confidence': code_confidence, 'doc_confidence': doc_confidence}
    elif code_score >= CODE_THRESHOLD:
        # Check if it looks like code
        return 'code', {**code_info, 'confidence': code_confidence}
    else:
        return 'document', {'doc_score': doc_score, 'confidence': doc_confidence}


def _is_spreadsheet_pattern(content: str) -> bool:
    """Check if content looks like CSV/Excel data."""
    lines = content.strip().split('\n')
    if len(lines) < 2:
        return False

    # Check for consistent column counts (CSV pattern)
    column_counts = []
    for line in lines[:20]:  # Check first 20 lines
        # Skip empty lines
        if not line.strip():
            continue
        # Count columns by comma
        cols = len(line.split(','))
        column_counts.append(cols)

    if len(column_counts) < 2:
        return False

    # Check if most lines have consistent column count
    from collections import Counter
    count_distribution = Counter(column_counts)
    most_common = count_distribution.most_common(1)

    # If most lines have same column count (>1), likely CSV
    if most_common:
        count, freq = most_common[0]
        if count > 1 and freq / len(column_counts) > 0.7:
            return True

    return False


def _analyze_spreadsheet(content: str) -> dict:
    """Analyze spreadsheet-like content."""
    lines = content.strip().split('\n')
    if not lines:
        return {}

    # Parse first line as headers
    headers = []
    if lines:
        headers = [h.strip() for h in lines[0].split(',')]

    # Count data rows
    data_rows = []
    for line in lines[1:]:
        if line.strip():
            data_rows.append(line)

    return {
        'column_count': len(headers) if headers else 1,
        'headers': headers,
        'data_row_count': len(data_rows),
        'has_headers': len(headers) > 0
    }


def _analyze_code_content(content: str) -> Tuple[float, dict]:
    """Analyze text for code-like patterns.

    Returns: (code_score, info_dict)
    Uses raw weighted count without normalization for consistent scoring.
    """
    patterns = {
        # Function/method definitions
        'function_def': (
            r'\b(def|func|function|pub fn|sub|private|public)\s+\w+',
            3.0
        ),
        # Type annotations - more specific to avoid false positives
        # Matches: def foo(x: int), var name: string, Class name, etc.
        'type_annotation': (
            r':\s*(?:[A-Z][a-zA-Z_]*|int|str|bool|float|void|string|double|long|List|Dict|Set|Tuple)\b',
            2.0
        ),
        # Import statements
        'import_stmt': (
            r'\b(import|include|using|require|from)\b',
            2.0
        ),
        # Control flow
        'control_flow': (
            r'\b(if|else|elif|for|while|switch|case|when)\b',
            1.5
        ),
        # Syntax markers
        'syntax_markers': (
            r'[{}()\[\];:=><>]',
            1.0
        ),
        # Class definitions
        'class_def': (
            r'\b(class|struct|interface|trait|enum)\s+\w+',
            2.5
        ),
        # Decorators/annotations
        'decorator': (
            r'@\w+\s*\(',
            2.0
        ),
        # Arrow functions
        'arrow_func': (
            r'=>',
            2.0
        ),
        # Variable assignment with type
        'typed_assignment': (
            r'(var|let|const|val|var)\s+\w+\s*[:=]',
            1.5
        ),
        # Return statements
        'return_stmt': (
            r'\b(return)\b',
            1.0
        ),
    }

    score = 0.0
    matches = {}

    for name, (pattern, weight) in patterns.items():
        count = len(re.findall(pattern, content, re.IGNORECASE))
        matches[name] = count
        score += count * weight

    words = re.findall(r'\b\w+\b', content)
    num_words = max(len(words), 10)  # Floor at 10 to prevent exploding scores on tiny snippets

    # Normalize by word count to reflect code syntax density rather than absolute volume
    normalized_score = (score / num_words) * 100

    return normalized_score, matches


def _analyze_document_content(content: str) -> float:
    """Analyze text for document-like (natural language) patterns."""
    # Remove code-like patterns first
    code_like = re.sub(r'[{}()\[\];:=<>]', ' ', content)

    # Common English words
    common_words = [
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose',
        'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
        'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
        'can', 'just', 'now', 'about', 'after', 'before', 'between',
        'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again',
        'further', 'then', 'once', 'here', 'there', 'any', 'while'
    ]

    # Count common word occurrences
    words = re.findall(r'\b\w+\b', content.lower())
    common_count = sum(1 for w in words if w in common_words)

    # Check for sentence-like patterns
    sentences = re.split(r'[.!?]+', content)
    avg_sentence_len = len(words) / max(len(sentences), 1)

    # Check for paragraph structure
    paragraphs = content.split('\n\n')
    avg_paragraph_len = len(content) / max(len(paragraphs), 1)

    # Score based on:
    # 1. High frequency of common words (natural language)
    # 2. Reasonable sentence length (not too short like code)
    # 3. Paragraph structure
    score = 0.0
    score += min(common_count / max(len(words), 1), 1.0) * 0.4
    score += min(max(10, min(25, avg_sentence_len)) / 25, 1.0) * 0.3
    score += min(max(50, min(500, avg_paragraph_len)) / 500, 1.0) * 0.3

    return score


def _ensure_hard_limit(chunks: List[ChunkResult], max_tokens: int) -> List[ChunkResult]:
    """Ensures every chunk in the list is strictly within max_tokens.

    This acts as the 'Last Resort Splitter'. If a chunk produced by semantic
    analysis is still too large, it is forcefully subdivided by tokens.
    """
    final_chunks = []
    for chunk in chunks:
        if count_tokens(chunk.text) <= max_tokens:
            final_chunks.append(chunk)
        else:
            sub_texts = split_text_by_tokens(chunk.text, max_tokens)
            current_line = chunk.line_start
            for text_part in sub_texts:
                line_count = text_part.count('\n')
                end_line = current_line + line_count
                final_chunks.append(ChunkResult(text=text_part, line_start=current_line, line_end=end_line))
                current_line = end_line
    return final_chunks

# =============================================================================
# Chunking Strategies
# =============================================================================

def _find_function_end(text: str, start_pos: int) -> int:
    """Find the end position of a function/class block starting at start_pos.

    Uses brace-depth counting for C-family/JS/Rust, falling back to
    indentation comparison for Python-style languages.
    """
    # Try brace-counting first (C, JS, Rust, Go, Java, etc.)
    has_opening_brace = '{' in text[start_pos:start_pos + 500]
    if has_opening_brace:
        depth = 0
        found_first = False
        for i, ch in enumerate(text[start_pos:], start=start_pos):
            if ch == '{':
                depth += 1
                found_first = True
            elif ch == '}':
                depth -= 1
                if found_first and depth == 0:
                    return i + 1
        return len(text)  # unclosed block — include to end

    # Indentation-based fallback (Python, YAML, etc.)
    lines = text[start_pos:].split('\n')
    if not lines:
        return len(text)

    # Find the indentation level of the declaration line
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    decl_indent = _indent(lines[0])
    char_pos = start_pos + len(lines[0]) + 1  # +1 for the newline

    for line in lines[1:]:
        stripped = line.strip()
        if stripped and _indent(line) <= decl_indent:
            # We've hit a sibling or parent — stop just before this line
            return char_pos
        char_pos += len(line) + 1

    return len(text)


def _split_mixed_content(text: str) -> List[tuple]:
    """Split text into alternating (type, content) segments.

    Returns a list of ('text', ...) or ('code', ...) tuples, where 'code'
    segments are the bodies of fenced markdown code blocks (``` or ~~~).
    """
    segments = []
    # Match fenced code blocks: ``` or ~~~ with optional language hint
    pattern = re.compile(r'(```[^\n]*\n.*?```|~~~[^\n]*\n.*?~~~)', re.DOTALL)
    last_end = 0
    for match in pattern.finditer(text):
        start, end = match.start(), match.end()
        if start > last_end:
            segments.append(('text', text[last_end:start]))
        # Strip the fence lines themselves; keep the inner code
        block = match.group(0)
        inner = '\n'.join(block.split('\n')[1:-1])
        segments.append(('code', inner))
        last_end = end
    if last_end < len(text):
        segments.append(('text', text[last_end:]))
    return segments


def chunk_code_text(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk code by function/class boundaries."""
    if not text:
        return []

    if count_tokens(text) <= max_tokens:
        return [ChunkResult(text=text, line_start=line_offset + 1, line_end=line_offset + 1 + text.count('\n'))]

    try:
        syntax_chunks = _chunk_by_code_structure(text, max_tokens, line_offset)
        if syntax_chunks and len(syntax_chunks) > 0:
            return syntax_chunks
    except Exception:
        pass

    chunks = []
    current_chunk = ""
    current_tokens = 0
    current_start_line = line_offset + 1

    lines = text.split('\n')
    line_cursor = line_offset + 1

    for line in lines:
        line_tokens = count_tokens(line)

        if current_tokens + line_tokens <= max_tokens:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line
                current_start_line = line_cursor
            current_tokens += line_tokens
        else:
            if current_chunk:
                chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))
                current_chunk = ""
                current_tokens = 0

            if line_tokens > max_tokens:
                words = line.split(' ')
                word_chunk = ""
                word_tokens = 0
                word_start_line = line_cursor

                for word in words:
                    word_tokens_count = count_tokens(word)
                    if word_tokens + word_tokens_count > max_tokens:
                        if word_chunk:
                            chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
                            word_chunk = ""
                            word_tokens = 0
                    word_chunk += (" " if word_chunk else "") + word
                    word_tokens += word_tokens_count

                if word_chunk:
                    chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
            else:
                current_chunk = line
                current_start_line = line_cursor
                current_tokens = line_tokens
        line_cursor += 1

    if current_chunk:
        chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [ChunkResult(text=text, line_start=line_offset+1, line_end=line_offset+1+text.count('\n'))]

def _chunk_by_code_structure(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk code by detecting function/class boundaries."""
    patterns = [
        (r'\b(def|class|function|pub fn|fun|func)\s+(\w+)', 0),
        (r'(?:^|\n)(?:static\s+)?(?:inline\s+)?(?:const\s+)?[a-zA-Z_][a-zA-Z0-9_::*<>,\s]*\s+(\w+)\s*\([^)]*\)\s*(?:const)?\s*\{', 0),
        (r'\w*\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', 0),
        (r'\b(interface|type|namespace|module)\s+(\w+)', 0),
    ]

    boundaries = [(0, 'start')]
    for pattern, _ in patterns:
        for match in re.finditer(pattern, text):
            start = match.start()
            end = _find_function_end(text, start)
            boundaries.append((start, 'function_start'))
            boundaries.append((end, 'function_end'))

    boundaries.sort()

    chunks = []
    current_chunk = ""
    current_start_pos = 0

    for i, (pos, marker) in enumerate(boundaries):
        segment = text[len(current_chunk):pos]

        if current_chunk and count_tokens(current_chunk) > max_tokens:
            if current_chunk.strip():
                start_line = line_offset + 1 + text.count('\n', 0, current_start_pos)
                chunks.append(ChunkResult(text=current_chunk.strip(), line_start=start_line, line_end=start_line + current_chunk.strip().count('\n')))
            current_chunk = segment
            current_start_pos = pos - len(segment)
        else:
            if not current_chunk:
                current_start_pos = pos - len(segment)
            current_chunk += segment

        if marker == 'function_start':
            func_end = _find_function_end(text, pos)
            func_text = text[pos:func_end]
            if not current_chunk:
                current_start_pos = pos
            current_chunk += func_text

    if current_chunk.strip():
        start_line = line_offset + 1 + text.count('\n', 0, current_start_pos)
        chunks.append(ChunkResult(text=current_chunk.strip(), line_start=start_line, line_end=start_line + current_chunk.strip().count('\n')))

    return _ensure_hard_limit(chunks, max_tokens)

def _chunk_by_lines(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk code by line count, respecting token limits."""
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_tokens = 0
    current_start_line = line_offset + 1
    line_cursor = line_offset + 1

    for line in lines:
        line_tokens = count_tokens(line)

        if line_tokens > max_tokens:
            if current_chunk:
                chunk_text = '\n'.join(current_chunk)
                chunks.append(ChunkResult(text=chunk_text, line_start=current_start_line, line_end=current_start_line + chunk_text.count('\n')))
                current_chunk = []
                current_tokens = 0

            words = line.split(' ')
            temp_chunk = []
            temp_tokens = 0
            word_start_line = line_cursor

            for word in words:
                word_tokens = count_tokens(word)
                if temp_tokens + word_tokens > max_tokens:
                    if temp_chunk:
                        chunk_text = '\n'.join(temp_chunk)
                        chunks.append(ChunkResult(text=chunk_text, line_start=word_start_line, line_end=word_start_line + chunk_text.count('\n')))
                    temp_chunk = [word]
                    temp_tokens = word_tokens
                else:
                    temp_chunk.append(word)
                    temp_tokens += word_tokens

            if temp_chunk:
                chunk_text = '\n'.join(temp_chunk)
                chunks.append(ChunkResult(text=chunk_text, line_start=word_start_line, line_end=word_start_line + chunk_text.count('\n')))
            line_cursor += 1
            continue

        if current_chunk and current_tokens + line_tokens > max_tokens:
            chunk_text = '\n'.join(current_chunk)
            chunks.append(ChunkResult(text=chunk_text, line_start=current_start_line, line_end=current_start_line + chunk_text.count('\n')))
            current_chunk = [line]
            current_tokens = line_tokens
            current_start_line = line_cursor
        else:
            if not current_chunk:
                current_start_line = line_cursor
            current_chunk.append(line)
            current_tokens += line_tokens
            
        line_cursor += 1

    if current_chunk:
        chunk_text = '\n'.join(current_chunk)
        chunks.append(ChunkResult(text=chunk_text, line_start=current_start_line, line_end=current_start_line + chunk_text.count('\n')))

    return _ensure_hard_limit(chunks, max_tokens)

def chunk_spreadsheet_text(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk spreadsheet data by rows."""
    lines = text.split('\n')
    if not lines:
        return []

    header = lines[0] if lines else ""
    header_tokens = count_tokens(header)
    data_lines = lines[1:]
    
    header_start_line = line_offset + 1

    if header_tokens > max_tokens:
        return [ChunkResult(text=header, line_start=header_start_line, line_end=header_start_line)]

    chunks = []
    current_chunk = [header]
    current_tokens = header_tokens
    current_start_line = header_start_line
    line_cursor = line_offset + 2

    for line in data_lines:
        if not line.strip():
            line_cursor += 1
            continue

        line_tokens = count_tokens(line)

        if current_tokens + line_tokens <= max_tokens:
            current_chunk.append(line)
            current_tokens += line_tokens
        else:
            chunks.append(ChunkResult(text='\n'.join(current_chunk), line_start=current_start_line, line_end=line_cursor - 1))

            if line_tokens > max_tokens:
                fields = line.split(',')
                temp_chunk = [header]
                temp_tokens = header_tokens
                temp_start_line = line_cursor

                for field in fields:
                    field_tokens = count_tokens(field)
                    if temp_tokens + field_tokens > max_tokens:
                        if len(temp_chunk) > 1:
                            chunks.append(ChunkResult(text='\n'.join(temp_chunk), line_start=temp_start_line, line_end=temp_start_line))
                            temp_chunk = [header]
                            temp_tokens = header_tokens
                    temp_chunk.append(field)
                    temp_tokens += field_tokens

                if len(temp_chunk) > 1:
                    chunks.append(ChunkResult(text='\n'.join(temp_chunk), line_start=temp_start_line, line_end=temp_start_line))
            else:
                current_chunk = [header, line]
                current_tokens = header_tokens + line_tokens
                current_start_line = line_cursor
        line_cursor += 1

    if current_chunk and len(current_chunk) > 1:
        chunks.append(ChunkResult(text='\n'.join(current_chunk), line_start=current_start_line, line_end=line_cursor - 1))

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [ChunkResult(text=header, line_start=header_start_line, line_end=header_start_line)]

def chunk_mixed_text(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk mixed content (text + code blocks)."""
    parts = _split_mixed_content(text)

    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    line_cursor = line_offset + 1
    current_start_line = line_cursor

    for part_type, content in parts:
        part_lines = content.count('\n')
        
        if part_type == 'code':
            if current_chunk:
                chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))
                current_chunk = ""
                current_tokens = 0

            part_chunks = chunk_code_text(content, max_tokens, line_offset=line_cursor - 1)
            chunks.extend(part_chunks)
        else:
            paragraphs = content.split('\n\n')
            para_cursor = line_cursor
            
            for para in paragraphs:
                para_stripped = para.strip()
                para_lines_count = para.count('\n')
                
                if not para_stripped:
                    para_cursor += para_lines_count + 2
                    continue

                para_tokens = count_tokens(para_stripped)

                if current_tokens + para_tokens <= max_tokens:
                    if current_chunk:
                        current_chunk += "\n\n" + para_stripped
                    else:
                        current_chunk = para_stripped
                        current_start_line = para_cursor
                    current_tokens += para_tokens
                else:
                    if current_chunk:
                        chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))
                        current_chunk = ""
                        current_tokens = 0

                    if para_tokens > max_tokens:
                        sentences = re.split(r'(?<=[.!?])\s+', para_stripped)
                        sentence_chunk = ""
                        sentence_tokens = 0
                        sentence_start_line = para_cursor

                        for sent in sentences:
                            sent_tokens = count_tokens(sent)

                            if sentence_tokens + sent_tokens <= max_tokens:
                                if sentence_chunk:
                                    sentence_chunk += " " + sent
                                else:
                                    sentence_chunk = sent
                                    sentence_start_line = para_cursor
                                sentence_tokens += sent_tokens
                            else:
                                if sentence_chunk:
                                    chunks.append(ChunkResult(text=sentence_chunk, line_start=sentence_start_line, line_end=sentence_start_line + sentence_chunk.count('\n')))
                                    sentence_chunk = ""
                                    sentence_tokens = 0

                                if sent_tokens > max_tokens:
                                    words = sent.split()
                                    word_chunk = ""
                                    word_tokens = 0
                                    word_start_line = para_cursor

                                    for word in words:
                                        word_tokens_count = count_tokens(word)
                                        if word_tokens + word_tokens_count > max_tokens:
                                            if word_chunk:
                                                chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
                                                word_chunk = ""
                                                word_tokens = 0
                                        word_chunk += (" " if word_chunk else "") + word
                                        word_tokens += word_tokens_count

                                    if word_chunk:
                                        chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
                                else:
                                    sentence_chunk = sent
                                    sentence_tokens = sent_tokens
                                    sentence_start_line = para_cursor

                        if sentence_chunk:
                            current_chunk = sentence_chunk
                            current_start_line = sentence_start_line
                            current_tokens = sentence_tokens
                    else:
                        current_chunk = para_stripped
                        current_start_line = para_cursor
                        current_tokens = para_tokens
                para_cursor += para_lines_count + 2
        line_cursor += part_lines

    if current_chunk:
        chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [ChunkResult(text=text, line_start=line_offset+1, line_end=line_offset+1+text.count('\n'))]

def chunk_document_text(text: str, max_tokens: int, line_offset: int = 0) -> List[ChunkResult]:
    """Chunk document text by paragraphs."""
    if not text:
        return []

    if count_tokens(text) <= max_tokens:
        return [ChunkResult(text=text, line_start=line_offset+1, line_end=line_offset+1+text.count('\n'))]

    chunks = []
    current_chunk = ""
    current_tokens = 0
    
    line_cursor = line_offset + 1
    current_start_line = line_cursor

    paragraphs = text.split('\n\n')

    for para in paragraphs:
        para_stripped = para.strip()
        para_lines_count = para.count('\n')
        
        if not para_stripped:
            line_cursor += para_lines_count + 2
            continue

        para_tokens = count_tokens(para_stripped)

        if current_tokens + para_tokens <= max_tokens:
            if current_chunk:
                current_chunk += "\n\n" + para_stripped
            else:
                current_chunk = para_stripped
                current_start_line = line_cursor
            current_tokens += para_tokens
        else:
            if current_chunk:
                chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))
                current_chunk = ""
                current_tokens = 0

            if para_tokens > max_tokens:
                sentences = re.split(r'(?<=[.!?])\s+', para_stripped)
                sentence_chunk = ""
                sentence_tokens = 0
                sentence_start_line = line_cursor

                for sent in sentences:
                    sent_tokens = count_tokens(sent)

                    if sentence_tokens + sent_tokens <= max_tokens:
                        if sentence_chunk:
                            sentence_chunk += " " + sent
                        else:
                            sentence_chunk = sent
                            sentence_start_line = line_cursor
                        sentence_tokens += sent_tokens
                    else:
                        if sentence_chunk:
                            chunks.append(ChunkResult(text=sentence_chunk, line_start=sentence_start_line, line_end=sentence_start_line + sentence_chunk.count('\n')))
                            sentence_chunk = ""
                            sentence_tokens = 0

                        if sent_tokens > max_tokens:
                            words = sent.split()
                            word_chunk = ""
                            word_tokens = 0
                            word_start_line = line_cursor

                            for word in words:
                                word_tokens_count = count_tokens(word)
                                if word_tokens + word_tokens_count > max_tokens:
                                    if word_chunk:
                                        chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
                                        word_chunk = ""
                                        word_tokens = 0
                                word_chunk += (" " if word_chunk else "") + word
                                word_tokens += word_tokens_count

                            if word_chunk:
                                chunks.append(ChunkResult(text=word_chunk, line_start=word_start_line, line_end=word_start_line + word_chunk.count('\n')))
                        else:
                            sentence_chunk = sent
                            sentence_tokens = sent_tokens
                            sentence_start_line = line_cursor

                if sentence_chunk:
                    current_chunk = sentence_chunk
                    current_start_line = sentence_start_line
                    current_tokens = sentence_tokens
            else:
                current_chunk = para_stripped
                current_start_line = line_cursor
                current_tokens = para_tokens
        line_cursor += para_lines_count + 2

    if current_chunk:
        chunks.append(ChunkResult(text=current_chunk, line_start=current_start_line, line_end=current_start_line + current_chunk.count('\n')))

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [ChunkResult(text=text, line_start=line_offset+1, line_end=line_offset+1+text.count('\n'))]

# =============================================================================
# Metadata Extraction
# =============================================================================

def extract_code_metadata(content: str, line_start: int = 1) -> dict:
    """Extract metadata from code content.

    Args:
        content: Code content
        line_start: Starting line number

    Returns:
        Dict with function names, class names, etc.
    """
    metadata = {
        'function_names': [],
        'class_names': [],
        'imports': [],
        'line_start': line_start,
        'line_end': line_start + len(content.split('\n')) - 1
    }

    # Extract function definitions
    func_patterns = [
        r'\bdef\s+(\w+)\s*\(',
        r'\bfunction\s+(\w+)\s*\(',
        r'\bfunc\s+(\w+)\s*\(',
        r'\b(pub\s+)?fn\s+(\w+)\s*\(',
        r'\bfun\s+(\w+)\s*\(',
    ]

    for pattern in func_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            if isinstance(match, tuple):
                metadata['function_names'].extend(match)
            else:
                metadata['function_names'].append(match)

    # Extract class definitions
    class_patterns = [
        r'\bclass\s+(\w+)',
        r'\bstruct\s+(\w+)',
        r'\binterface\s+(\w+)',
        r'\btrait\s+(\w+)',
        r'\benum\s+(\w+)',
    ]

    for pattern in class_patterns:
        matches = re.findall(pattern, content)
        metadata['class_names'].extend(matches)

    # Extract imports
    import_patterns = [
        r'\b(import\s+[\w.*]+)',
        r'\b(from\s+[\w.]+\s+import)',
        r'\b(include\s+["<][^">]+[">])',
        r'\b(using\s+[\w.]+)',
        r'\b(require\s+[\w./]+)',
    ]

    for pattern in import_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        metadata['imports'].extend(matches)

    return metadata


def extract_document_metadata(content: str) -> dict:
    """Extract metadata from document content.

    Args:
        content: Document text

    Returns:
        Dict with section headers, etc.
    """
    metadata = {
        'section_headers': [],
        'subsection_headers': [],
        'has_title': False
    }

    # Detect title (first line, often formatted differently)
    lines = content.split('\n')
    if lines:
        first_line = lines[0].strip()
        # Title patterns: all caps, short, often followed by blank line
        if len(first_line) < 100 and first_line.isupper():
            metadata['section_headers'].append(first_line)
            metadata['has_title'] = True

    # Detect section headers (lines starting with # or ===, ---)
    header_patterns = [
        (r'^#\s+(.+)$', 'section_headers'),           # Markdown h1
        (r'^##\s+(.+)$', 'subsection_headers'),       # Markdown h2
        (r'^###\s+(.+)$', 'subsection_headers'),      # Markdown h3
        (r'^(.+)\n=+$', 'section_headers'),           # Underlined h1
        (r'^(.+)\n-+$', 'subsection_headers'),        # Underlined h2
    ]

    for pattern, field in header_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        metadata[field].extend(matches)

    return metadata
