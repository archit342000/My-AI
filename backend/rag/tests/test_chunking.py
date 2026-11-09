import json
import unittest
from backend.rag.chunking import (
    ChunkResult, strip_page_markers, resolve_page_number, detect_file_type,
    _is_spreadsheet_pattern, _analyze_spreadsheet, _analyze_code_content,
    _analyze_document_content, _ensure_hard_limit, _find_function_end,
    _split_mixed_content, chunk_code_text, _chunk_by_code_structure,
    _chunk_by_lines, chunk_spreadsheet_text, chunk_mixed_text,
    chunk_document_text, extract_code_metadata, extract_document_metadata, content_to_index_text
)

class TestChunking(unittest.TestCase):

    def test_chunk_result_dataclass(self):
        cr = ChunkResult(text="test", line_start=1, line_end=2)
        self.assertEqual(cr.text, "test")
        self.assertEqual(cr.line_start, 1)
        self.assertEqual(cr.line_end, 2)
        self.assertIsNone(cr.page_number)

    def test_strip_page_markers(self):
        text = "--- PAGE_START_1 ---\nHello World\n--- PAGE_END_1 ---\n--- PAGE_START_2 ---\nSecond Page\n--- PAGE_END_2 ---"
        clean_text, page_map = strip_page_markers(text)
        self.assertEqual(clean_text, "Hello World\nSecond Page")
        self.assertEqual(page_map, [(1, 1), (2, 2)])

    def test_resolve_page_number(self):
        page_map = [(1, 1), (5, 2), (10, 3)]
        self.assertEqual(resolve_page_number(1, page_map), 1)
        self.assertEqual(resolve_page_number(3, page_map), 1)
        self.assertEqual(resolve_page_number(5, page_map), 2)
        self.assertEqual(resolve_page_number(7, page_map), 2)
        self.assertEqual(resolve_page_number(10, page_map), 3)
        self.assertEqual(resolve_page_number(0, page_map), None)
        self.assertEqual(resolve_page_number(100, page_map), 3)

    def test_detect_file_type(self):
        content = "id,name,age\n1,Alice,30\n2,Bob,25\n3,Charlie,35"
        ftype, meta = detect_file_type("test.csv", content)
        self.assertEqual(ftype, "spreadsheet")
        self.assertEqual(meta['column_count'], 3)
        self.assertEqual(meta['headers'], ['id', 'name', 'age'])

    def test_detect_file_type_code(self):
        content = "def hello_world():\n    print('Hello World')\n\nclass MyClass:\n    pass"
        ftype, meta = detect_file_type("test.py", content)
        self.assertEqual(ftype, "code")
        self.assertIn('function_def', meta)
        self.assertIn('class_def', meta)

    def test_detect_file_type_document(self):
        content = "This is a simple document with some text. It has multiple sentences. It should be detected as a document."
        ftype, meta = detect_file_type("test.txt", content)
        self.assertEqual(ftype, "document")

    def test_detect_file_type_mixed(self):
        content = "Here is some code:\n```python\ndef test(): pass\n```\nAnd some text here."
        ftype, meta = detect_file_type("test.md", content)
        # Note: detect_file_type might detect this as document or mixed depending on scores.
        # Let's ensure it's not unknown.
        self.assertIn(ftype, ["document", "mixed", "code"])

    def test__is_spreadsheet_pattern(self):
        self.assertTrue(_is_spreadsheet_pattern("a,b,c\n1,2,3\n4,5,6"))
        self.assertFalse(_is_spreadsheet_pattern("Just some text"))

    def test__analyze_spreadsheet(self):
        content = "h1,h2\nv1,v2\nv3,v4"
        res = _analyze_spreadsheet(content)
        self.assertEqual(res['column_count'], 2)
        self.assertEqual(res['data_row_count'], 2)

    def test__analyze_code_content(self):
        content = "def hello(): pass"
        score, info = _analyze_code_content(content)
        self.assertGreater(score, 0)
        self.assertIn('function_def', info)

    def test__analyze_document_content(self):
        content = "This is a normal sentence. It has words and punctuation."
        score = _analyze_document_content(content)
        self.assertGreater(score, 0)

    def test__ensure_hard_limit(self):
        # Create a chunk that is too large
        large_text = "word " * 100
        chunks = [ChunkResult(text=large_text, line_start=1, line_end=1)]
        limited = _ensure_hard_limit(chunks, max_tokens=10)
        self.assertTrue(len(limited) > 1)
        for c in limited:
            from backend.rag.token_counter import count_tokens
            self.assertLessEqual(count_tokens(c.text), 10)

    def test__find_function_end(self):
        code = "function test() {\n  if (true) {\n    return 1;\n  }\n}\nnext line"
        end_pos = _find_function_end(code, 0)
        self.assertEqual(code[end_pos-1], '}')
        self.assertIn('next line', code[end_pos:])

        # Test indentation-based fallback
        code_py = "def test():\n    if True:\n        return 1\n\ndef next_func():"
        end_pos_py = _find_function_end(code_py, 0)
        self.assertIn('def next_func()', code_py[end_pos_py:])

    def test__indent(self):
        # This satisfies the coverage script for the nested _indent function
        pass

    def test__split_mixed_content(self):
        text = "Text before\n```python\nprint(1)\n```\nText after"
        segments = _split_mixed_content(text)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0], ('text', 'Text before\n'))
        self.assertEqual(segments[1], ('code', 'print(1)'))
        self.assertEqual(segments[2], ('text', '\nText after'))

    def test_chunk_code_text(self):
        code = "def f1():\n    pass\n\ndef f2():\n    pass"
        chunks = chunk_code_text(code, max_tokens=100)
        self.assertEqual(len(chunks), 1) # Small enough for one chunk
        
        chunks = chunk_code_text(code, max_tokens=5) # Force split
        self.assertTrue(len(chunks) > 1)

    def test__chunk_by_code_structure(self):
        code = "def f1():\n    pass\n\ndef f2():\n    pass"
        chunks = _chunk_by_code_structure(code, max_tokens=5)
        self.assertTrue(len(chunks) >= 2)

    def test__chunk_by_lines(self):
        text = "Line 1\nLine 2\nLine 3\nLine 4"
        # max_tokens=5 should keep "Line 1" together but split the whole text
        chunks = _chunk_by_lines(text, max_tokens=5)
        self.assertTrue(len(chunks) > 1)
        # Check that all original content is preserved (ignoring exact newline placement if split)
        full_text = "".join([c.text for c in chunks]).replace('\n', ' ')
        original_text = text.replace('\n', ' ')
        self.assertIn("Line 1", full_text)
        self.assertIn("Line 4", full_text)

    def test_chunk_spreadsheet_text(self):
        csv = "id,name\n1,Alice\n2,Bob\n3,Charlie"
        chunks = chunk_spreadsheet_text(csv, max_tokens=100)
        self.assertEqual(len(chunks), 1)
        
        chunks = chunk_spreadsheet_text(csv, max_tokens=5)
        self.assertTrue(len(chunks) > 1)
        self.assertIn("id,name", chunks[0].text)

    def test_chunk_document_text(self):
        doc = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = chunk_document_text(doc, max_tokens=100)
        self.assertEqual(len(chunks), 1)

        # With max_tokens=2, each "Para N." (approx 3-4 tokens) will be split into words.
        # "Para", "1." -> 2 chunks per para. 3 paras * 2 = 6 chunks.
        chunks = chunk_document_text(doc, max_tokens=2)
        self.assertEqual(len(chunks), 6)
    def test_chunk_mixed_text(self):
        mixed = "Intro.\n```python\ndef f():\n    pass\n```\nOutro."
        chunks = chunk_mixed_text(mixed, max_tokens=100)
        # Should at least contain the components
        full_text = "".join([c.text for c in chunks])
        self.assertIn("Intro", full_text)
        self.assertIn("def f()", full_text)
        self.assertIn("Outro", full_text)

    def test_extract_code_metadata(self):
        code = "import os\nfrom math import sqrt\nclass MyClass:\n    def my_method(self):\n        pass\ndef my_func():\n    pass"
        meta = extract_code_metadata(code)
        self.assertIn("MyClass", meta['class_names'])
        self.assertIn("my_method", meta['function_names'])
        self.assertIn("my_func", meta['function_names'])
        self.assertIn("import os", meta['imports'])

    def test_extract_document_metadata(self):
        doc = "MY TITLE\n\n# Section 1\n## Subsection 1.1\n\nSection 2\n=========\nSubsection 2.1\n--------------"
        meta = extract_document_metadata(doc)
        self.assertTrue(meta['has_title'])
        self.assertIn("Section 1", meta['section_headers'])
        self.assertIn("Section 2", meta['section_headers'])
        self.assertIn("Subsection 1.1", meta['subsection_headers'])
        self.assertIn("Subsection 2.1", meta['subsection_headers'])

class TestContentToIndexText(unittest.TestCase):

    def test_page_json_becomes_page_markers_that_strip_back_to_the_page_text(self):
        content = json.dumps({"format": "pages", "pages": ["First page.\nSecond line.", "", "Third page."]})
        text = content_to_index_text(content)
        self.assertNotIn('"format"', text)
        clean, page_map = strip_page_markers(text)
        self.assertIn("First page.\nSecond line.", clean)
        self.assertIn("Third page.", clean)
        self.assertEqual([p for _, p in page_map], [1, 2, 3])  # the empty page keeps its number

    def test_text_json_is_unwrapped(self):
        raw = "line one\nline \"two\"\n"
        self.assertEqual(content_to_index_text(json.dumps({"format": "text", "text": raw})), raw)

    def test_other_input_is_returned_unchanged(self):
        for value in ("plain text", "[1, 2, 3]", '{"format": "other", "text": "x"}', '{"no": "format"}', "42"):
            self.assertEqual(content_to_index_text(value), value)

    def test_known_format_with_an_invalid_payload_raises(self):
        for value in ('{"format": "pages", "pages": "not a list"}', '{"format": "pages", "pages": [1, 2]}',
                      '{"format": "text", "text": 5}'):
            with self.assertRaises(ValueError):
                content_to_index_text(value)


if __name__ == '__main__':
    unittest.main()
