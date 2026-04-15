"""Tests for backend.chunking module - content-based file type detection."""

import pytest
from backend.chunking import (
    detect_file_type,
    _analyze_code_content,
    _analyze_document_content,
    extract_code_metadata,
    extract_document_metadata,
    chunk_code_text,
    chunk_spreadsheet_text,
)


class TestFileDetectType:
    """Tests for detect_file_type function."""

    def test_detect_python_code(self):
        """Python files should be detected as code."""
        code_content = """
def hello():
    print('Hello World')

class MyClass:
    def __init__(self):
        pass
"""
        file_type, meta = detect_file_type('test.py', code_content)
        assert file_type == 'code'

    def test_detect_javascript_code(self):
        """JavaScript files should be detected as code."""
        code_content = """
function greet(name) {
    console.log('Hello, ' + name);
}

class Person {
    constructor(name) {
        this.name = name;
    }
}
"""
        file_type, meta = detect_file_type('app.js', code_content)
        assert file_type == 'code'

    def test_detect_typescript_code(self):
        """TypeScript files should be detected as code."""
        code_content = """
interface User {
    name: string;
    age: number;
}

function greet(user: User): void {
    console.log(user.name);
}
"""
        file_type, meta = detect_file_type('types.ts', code_content)
        assert file_type == 'code'

    def test_detect_spreadsheet_csv(self):
        """CSV files should be detected as spreadsheet."""
        csv_content = """name,age,city
John,25,NYC
Jane,30,LA
Bob,35,Chicago"""
        file_type, meta = detect_file_type('data.csv', csv_content)
        assert file_type == 'spreadsheet'
        assert meta.get('column_count') == 3
        assert meta.get('has_headers') is True

    def test_detect_spreadsheet_with_headers(self):
        """CSV with headers should be detected correctly."""
        csv_content = """id,name,email
1,Alice,alice@example.com
2,Bob,bob@example.com"""
        file_type, meta = detect_file_type('users.csv', csv_content)
        assert file_type == 'spreadsheet'
        assert meta.get('headers') == ['id', 'name', 'email']
        # column_headers is added in RAG store, not in _analyze_spreadsheet

    def test_detect_document(self):
        """Natural language documents should be detected as document."""
        doc_content = """This is a document.
It has multiple paragraphs.
The second paragraph follows after a blank line.

Another paragraph with more information."""
        file_type, meta = detect_file_type('document.txt', doc_content)
        assert file_type == 'document'

    def test_detect_mixed_content(self):
        """Content with both code and document patterns should be mixed."""
        mixed_content = """This is a document with some code.

```python
def hello():
    print('Hello')
```

More text here."""
        file_type, meta = detect_file_type('mixed.md', mixed_content)
        assert file_type == 'mixed'
        assert 'code_info' in meta

    def test_detect_short_code_snippet(self):
        """Short code snippets should still be detected as code."""
        short_code = """def foo():
    return 42"""
        file_type, meta = detect_file_type('short.py', short_code)
        assert file_type == 'code'

    def test_detect_empty_content(self):
        """Empty or very short content should be unknown."""
        file_type, meta = detect_file_type('empty.txt', '')
        assert file_type == 'unknown'
        assert meta == {}

        file_type, meta = detect_file_type('tiny.txt', 'hi')
        assert file_type == 'unknown'

    def test_code_score_threshold(self):
        """Code score should be >= 3 for code files."""
        code_content = """def hello():
    pass"""
        score, info = _analyze_code_content(code_content)
        assert score >= 3.0

    def test_document_score_below_threshold(self):
        """Document content should have code score below threshold."""
        doc_content = """This is a simple document.
It contains natural language text.
No code patterns should be detected."""
        score, info = _analyze_code_content(doc_content)
        assert score < 3.0


class TestCodeMetadataExtraction:
    """Tests for extract_code_metadata function."""

    def test_extract_function_names(self):
        """Should extract function names correctly."""
        code = """def hello():
    pass

def world(name):
    return name"""
        meta = extract_code_metadata(code)
        assert 'hello' in meta['function_names']
        assert 'world' in meta['function_names']

    def test_extract_class_names(self):
        """Should extract class names correctly."""
        code = """class MyClass:
    pass

class AnotherClass:
    pass"""
        meta = extract_code_metadata(code)
        assert 'MyClass' in meta['class_names']
        assert 'AnotherClass' in meta['class_names']

    def test_extract_imports(self):
        """Should extract import statements."""
        code = """import os
from pathlib import Path
import sys"""
        meta = extract_code_metadata(code)
        assert len(meta['imports']) > 0

    def test_extract_line_numbers(self):
        """Should calculate line numbers correctly."""
        code = """line 1
line 2
line 3"""
        meta = extract_code_metadata(code, line_start=10)
        assert meta['line_start'] == 10
        assert meta['line_end'] == 12  # 10 + 3 - 1


class TestDocumentMetadataExtraction:
    """Tests for extract_document_metadata function."""

    def test_extract_section_headers(self):
        """Should extract section headers."""
        doc = """# Introduction
Some text here.

## Background
More text.
"""
        meta = extract_document_metadata(doc)
        assert 'Introduction' in meta['section_headers']
        assert 'Background' in meta['subsection_headers']

    def test_extract_title(self):
        """Should detect title (uppercase first line)."""
        doc = """MY DOCUMENT TITLE
=================
Some content here."""
        meta = extract_document_metadata(doc)
        assert meta['has_title'] is True


class TestChunkCodeText:
    """Tests for chunk_code_text function."""

    def test_chunk_by_structure(self):
        """Should chunk by function/class boundaries."""
        code = """def func1():
    pass

def func2():
    pass

class MyClass:
    pass
"""
        chunks = chunk_code_text(code, max_tokens=500)
        assert len(chunks) >= 1

    def test_empty_code(self):
        """Empty code should return empty list."""
        chunks = chunk_code_text('', max_tokens=500)
        assert chunks == []


class TestChunkSpreadsheetText:
    """Tests for chunk_spreadsheet_text function."""

    def test_chunk_with_headers(self):
        """Should include header row in each chunk."""
        csv = """name,age,city
John,25,NYC
Jane,30,LA
Bob,35,Chicago"""
        chunks = chunk_spreadsheet_text(csv, max_tokens=500)
        assert len(chunks) >= 1
        # First chunk should have header
        assert 'name,age,city' in chunks[0]
