"""
Chunking Module - Content-based file type detection and adaptive chunking.

This module provides:
- File type detection based on content analysis (not just extension)
- Syntax-aware chunking for code files
- Row-based chunking for spreadsheet data
- Hybrid chunking for mixed content
"""
import re
from typing import Tuple, List, Dict, Optional

from backend.token_counter import count_tokens, split_text_by_tokens
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


def _ensure_hard_limit(chunks: List[str], max_tokens: int) -> List[str]:
    """Ensures every chunk in the list is strictly within max_tokens.

    This acts as the 'Last Resort Splitter'. If a chunk produced by semantic
    analysis is still too large, it is forcefully subdivided by tokens.

    Args:
        chunks: List of chunks to verify
        max_tokens: Maximum allowed tokens

    Returns:
        List of chunks where ALL are <= max_tokens
    """
    final_chunks = []
    for chunk in chunks:
        if count_tokens(chunk) <= max_tokens:
            final_chunks.append(chunk)
        else:
            # Atomic split by tokens
            final_chunks.extend(split_text_by_tokens(chunk, max_tokens))
    return final_chunks


# =============================================================================
# Chunking Strategies
# =============================================================================

def chunk_code_text(text: str, max_tokens: int) -> List[str]:
    """Chunk code by function/class boundaries.

    Guarantees that no chunk exceeds max_tokens. Structure (functions/classes)
    is respected when possible, but token limits always take priority.

    Args:
        text: Code text to chunk
        max_tokens: Maximum tokens per chunk

    Returns:
        List of code chunks, each within max_tokens limit
    """
    if not text:
        return []

    # Single chunk fits
    if count_tokens(text) <= max_tokens:
        return [text]

    # Try syntax-aware chunking first (respects function/class boundaries)
    try:
        syntax_chunks = _chunk_by_code_structure(text, max_tokens)
        # Only use syntax chunks if they produce reasonable results
        if syntax_chunks and len(syntax_chunks) > 0:
            return syntax_chunks
    except Exception:
        # Fall back to line-based chunking if syntax parsing fails
        pass

    # Fallback to line-based chunking
    chunks = []
    current_chunk = ""
    current_tokens = 0

    # Split by lines
    lines = text.split('\n')

    for line in lines:
        line_tokens = count_tokens(line)

        # Line fits as-is
        if current_tokens + line_tokens <= max_tokens:
            if current_chunk:
                current_chunk += "\n" + line
            else:
                current_chunk = line
            current_tokens += line_tokens
        else:
            # Current chunk is full, save it
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0

            # If line itself exceeds limit, split by words
            if line_tokens > max_tokens:
                words = line.split(' ')
                word_chunk = ""
                word_tokens = 0

                for word in words:
                    word_tokens_count = count_tokens(word)

                    if word_tokens + word_tokens_count > max_tokens:
                        if word_chunk:
                            chunks.append(word_chunk)
                            word_chunk = ""
                            word_tokens = 0

                    word_chunk += (" " if word_chunk else "") + word
                    word_tokens += word_tokens_count

                # Save remaining words
                if word_chunk:
                    chunks.append(word_chunk)
            else:
                # Line fits, start new chunk
                current_chunk = line
                current_tokens = line_tokens

    # Save remaining chunk
    if current_chunk:
        chunks.append(current_chunk)

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [text]


def _chunk_by_code_structure(text: str, max_tokens: int) -> List[str]:
    """Chunk code by detecting function/class boundaries."""
    # Patterns for function/class starts
    patterns = [
        # Python/Java/C#/JavaScript
        (r'\b(def|class|function|pub fn|fun|func)\s+(\w+)', 0),
        # C/C++/Java style
        (r'(?:^|\n)(?:static\s+)?(?:inline\s+)?(?:const\s+)?[a-zA-Z_][a-zA-Z0-9_::*<>,\s]*\s+(\w+)\s*\([^)]*\)\s*(?:const)?\s*\{', 0),
        # Arrow functions
        (r'\w*\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', 0),
        # TypeScript interfaces/types
        (r'\b(interface|type|namespace|module)\s+(\w+)', 0),
    ]

    # Find all function/class boundaries
    boundaries = [(0, 'start')]

    for pattern, _ in patterns:
        for match in re.finditer(pattern, text):
            start = match.start()
            # Find the end of this function (roughly by brace matching)
            end = _find_function_end(text, start)
            boundaries.append((start, 'function_start'))
            boundaries.append((end, 'function_end'))

    # Sort boundaries
    boundaries.sort()

    # Try to create chunks within boundaries
    chunks = []
    current_chunk = ""

    for i, (pos, marker) in enumerate(boundaries):
        segment = text[len(current_chunk):pos]

        if current_chunk and count_tokens(current_chunk) > max_tokens:
            # Current chunk is too large, save it and start new
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = segment
        else:
            current_chunk += segment

        # Include the function header with its content
        if marker == 'function_start':
            func_end = _find_function_end(text, pos)
            current_chunk += text[pos:func_end]

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return _ensure_hard_limit(chunks, max_tokens)


def _find_function_end(text: str, start: int) -> int:
    """Find the end of a function starting at position start."""
    # Find opening brace
    brace_start = text.find('{', start)
    if brace_start == -1:
        # No braces, find end of line
        return text.find('\n', start)

    # Match braces
    depth = 1
    pos = brace_start + 1
    while pos < len(text) and depth > 0:
        if text[pos] == '{':
            depth += 1
        elif text[pos] == '}':
            depth -= 1
        pos += 1

    return pos


def _chunk_by_lines(text: str, max_tokens: int) -> List[str]:
    """Chunk code by line count, respecting token limits.

    Ensures no chunk exceeds max_tokens. If a single line exceeds max_tokens,
    it will be split further by words to stay within limits.
    """
    lines = text.split('\n')
    chunks = []
    current_chunk = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)

        # If a single line exceeds max_tokens, we need to split it further
        if line_tokens > max_tokens:
            # First, save current chunk if it has content
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_tokens = 0

            # Split the long line by spaces into words
            # Build chunks word by word until hitting the limit
            words = line.split(' ')
            temp_chunk = []
            temp_tokens = 0

            for word in words:
                word_tokens = count_tokens(word)

                if temp_tokens + word_tokens > max_tokens:
                    # Save current temp_chunk and start new
                    if temp_chunk:
                        chunks.append('\n'.join(temp_chunk))
                    temp_chunk = [word]
                    temp_tokens = word_tokens
                else:
                    temp_chunk.append(word)
                    temp_tokens += word_tokens

            # Handle remaining words
            if temp_chunk:
                chunks.append('\n'.join(temp_chunk))
            continue

        # Normal case: check if adding this line would exceed max_tokens
        if current_chunk and current_tokens + line_tokens > max_tokens:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens

    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return _ensure_hard_limit(chunks, max_tokens)


def chunk_spreadsheet_text(text: str, max_tokens: int) -> List[str]:
    """Chunk spreadsheet data by rows.

    Keeps header row with each chunk for context. Guarantees that no chunk
    exceeds max_tokens.

    Args:
        text: CSV/Excel-like text
        max_tokens: Maximum tokens per chunk

    Returns:
        List of row-based chunks
    """
    lines = text.split('\n')
    if not lines:
        return []

    # Extract header
    header = lines[0] if lines else ""
    header_tokens = count_tokens(header)
    data_lines = lines[1:]

    # If header alone exceeds limit, return it as single chunk
    # (this shouldn't happen with proper config)
    if header_tokens > max_tokens:
        return [header]

    chunks = []
    current_chunk = [header]
    current_tokens = header_tokens

    for line in data_lines:
        if not line.strip():
            continue

        line_tokens = count_tokens(line)

        # Line fits as-is
        if current_tokens + line_tokens <= max_tokens:
            current_chunk.append(line)
            current_tokens += line_tokens
        else:
            # Current chunk is full, save it
            chunks.append('\n'.join(current_chunk))

            # If line itself exceeds limit, split by fields/words
            if line_tokens > max_tokens:
                # Split by commas (CSV fields) first
                fields = line.split(',')
                temp_chunk = [header]
                temp_tokens = header_tokens

                for field in fields:
                    field_tokens = count_tokens(field)

                    if temp_tokens + field_tokens > max_tokens:
                        if len(temp_chunk) > 1:  # Has data rows
                            chunks.append('\n'.join(temp_chunk))
                            temp_chunk = [header]
                            temp_tokens = header_tokens

                    temp_chunk.append(field)
                    temp_tokens += field_tokens

                # Save remaining fields
                if len(temp_chunk) > 1:
                    chunks.append('\n'.join(temp_chunk))
            else:
                # Line fits, start new chunk
                current_chunk = [header, line]
                current_tokens = header_tokens + line_tokens

    # Save remaining chunk
    if current_chunk and len(current_chunk) > 1:
        chunks.append('\n'.join(current_chunk))

    # Final hard-limit guarantee
    return _ensure_hard_limit(chunks, max_tokens) if chunks else [header]


def chunk_mixed_text(text: str, max_tokens: int) -> List[str]:
    """Chunk mixed content (text + code blocks).

    Detects code blocks (fenced with backticks or indented) and chunks
    them separately from surrounding text. Guarantees that no chunk exceeds
    max_tokens.

    Args:
        text: Mixed content text
        max_tokens: Maximum tokens per chunk

    Returns:
        List of chunks
    """
    # Try to detect fenced code blocks
    parts = _split_mixed_content(text)

    chunks = []
    current_chunk = ""
    current_tokens = 0

    for part_type, content in parts:
        if part_type == 'code':
            # Process any accumulated text first
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0

            # Chunk code content (which guarantees limits)
            part_chunks = chunk_code_text(content, max_tokens)
            chunks.extend(part_chunks)
        else:
            # For non-code parts, use paragraph-based chunking with hard limits
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                para_stripped = para.strip()
                if not para_stripped:
                    continue

                para_tokens = count_tokens(para_stripped)

                # Paragraph fits as-is
                if current_tokens + para_tokens <= max_tokens:
                    if current_chunk:
                        current_chunk += "\n\n" + para_stripped
                    else:
                        current_chunk = para_stripped
                    current_tokens += para_tokens
                else:
                    # Current chunk is full, save it
                    if current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = ""
                        current_tokens = 0

                    # If paragraph exceeds limit, split by sentences
                    if para_tokens > max_tokens:
                        sentences = re.split(r'(?<=[.!?])\s+', para_stripped)
                        sentence_chunk = ""
                        sentence_tokens = 0

                        for sent in sentences:
                            sent_tokens = count_tokens(sent)

                            if sentence_tokens + sent_tokens <= max_tokens:
                                if sentence_chunk:
                                    sentence_chunk += " " + sent
                                else:
                                    sentence_chunk = sent
                                sentence_tokens += sent_tokens
                            else:
                                if sentence_chunk:
                                    chunks.append(sentence_chunk)
                                    sentence_chunk = ""
                                    sentence_tokens = 0

                                # Split sentence by words if needed
                                if sent_tokens > max_tokens:
                                    words = sent.split()
                                    word_chunk = ""
                                    word_tokens = 0

                                    for word in words:
                                        word_tokens_count = count_tokens(word)

                                        if word_tokens + word_tokens_count > max_tokens:
                                            if word_chunk:
                                                chunks.append(word_chunk)
                                                word_chunk = ""
                                                word_tokens = 0

                                        word_chunk += (" " if word_chunk else "") + word
                                        word_tokens += word_tokens_count

                                    if word_chunk:
                                        chunks.append(word_chunk)
                                else:
                                    sentence_chunk = sent
                                    sentence_tokens = sent_tokens

                        if sentence_chunk:
                            current_chunk = sentence_chunk
                            current_tokens = sentence_tokens
                    else:
                        current_chunk = para_stripped
                        current_tokens = para_tokens

    # Save remaining chunk
    if current_chunk:
        chunks.append(current_chunk)

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [text]


def _split_mixed_content(text: str) -> List[Tuple[str, str]]:
    """Split text into code and non-code parts."""
    parts = []

    # Pattern for fenced code blocks
    fenced_pattern = r'(```[\w]*\n)([\s\S]*?)(```|$)'

    last_end = 0
    for match in re.finditer(fenced_pattern, text):
        # Add text before code block
        if match.start() > last_end:
            before = text[last_end:match.start()]
            if before.strip():
                parts.append(('text', before))

        # Add code block
        code = match.group(2)  # Content inside backticks
        parts.append(('code', code))
        last_end = match.end()

    # Add remaining text
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining.strip():
            parts.append(('text', remaining))

    # If no code blocks found, treat entire text as document
    if not parts:
        parts.append(('text', text))

    return parts


def chunk_document_text(text: str, max_tokens: int) -> List[str]:
    """Chunk document text by paragraphs.

    Guarantees that no chunk exceeds max_tokens. Paragraph structure is
    respected when possible, but token limits always take priority.

    Args:
        text: Document text
        max_tokens: Maximum tokens per chunk

    Returns:
        List of paragraph-based chunks
    """
    if not text:
        return []

    # Single chunk fits
    if count_tokens(text) <= max_tokens:
        return [text]

    chunks = []
    current_chunk = ""
    current_tokens = 0

    # Split by paragraphs
    paragraphs = text.split('\n\n')

    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue

        para_tokens = count_tokens(para_stripped)

        # Paragraph fits as-is
        if current_tokens + para_tokens <= max_tokens:
            if current_chunk:
                current_chunk += "\n\n" + para_stripped
            else:
                current_chunk = para_stripped
            current_tokens += para_tokens
        else:
            # Current chunk is full, save it
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0

            # If paragraph itself exceeds limit, split by sentences
            if para_tokens > max_tokens:
                # Split paragraph into sentences
                sentences = re.split(r'(?<=[.!?])\s+', para_stripped)
                sentence_chunk = ""
                sentence_tokens = 0

                for sent in sentences:
                    sent_tokens = count_tokens(sent)

                    # Sentence fits as-is
                    if sentence_tokens + sent_tokens <= max_tokens:
                        if sentence_chunk:
                            sentence_chunk += " " + sent
                        else:
                            sentence_chunk = sent
                        sentence_tokens += sent_tokens
                    else:
                        # Sentence chunk full, save it
                        if sentence_chunk:
                            chunks.append(sentence_chunk)
                            sentence_chunk = ""
                            sentence_tokens = 0

                        # If sentence still exceeds limit, split by words
                        if sent_tokens > max_tokens:
                            words = sent.split()
                            word_chunk = ""
                            word_tokens = 0

                            for word in words:
                                word_tokens_count = count_tokens(word)

                                if word_tokens + word_tokens_count > max_tokens:
                                    if word_chunk:
                                        chunks.append(word_chunk)
                                        word_chunk = ""
                                        word_tokens = 0

                                word_chunk += (" " if word_chunk else "") + word
                                word_tokens += word_tokens_count

                            # Save remaining words
                            if word_chunk:
                                chunks.append(word_chunk)
                        else:
                            sentence_chunk = sent
                            sentence_tokens = sent_tokens

                # Save remaining sentence chunk
                if sentence_chunk:
                    current_chunk = sentence_chunk
                    current_tokens = sentence_tokens
            else:
                # Paragraph fits, start new chunk
                current_chunk = para_stripped
                current_tokens = para_tokens

    # Save remaining chunk
    if current_chunk:
        chunks.append(current_chunk)

    return _ensure_hard_limit(chunks, max_tokens) if chunks else [text]


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
