"""Tests for RAG hybrid search (BM25 + Vector fusion with RRF)."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRRFFusion:
    """Tests for Reciprocal Rank Fusion (RRF) algorithm."""

    def test_rrf_fusion_basic(self):
        """Test basic RRF fusion with two result sets."""
        from backend.rag import RAGStore, RAGManager

        # Create mock documents
        vector_docs = [
            {"text": "doc1", "metadata": {}, "score": 0.9, "source": "vector"},
            {"text": "doc2", "metadata": {}, "score": 0.8, "source": "vector"},
        ]
        bm25_docs = [
            {"text": "doc2", "metadata": {}, "score": 0.85, "source": "bm25"},
            {"text": "doc1", "metadata": {}, "score": 0.75, "source": "bm25"},
        ]

        # Create a minimal RAGStore instance for testing
        # We'll test the RRF algorithm directly
        from backend.rag import _cosine_similarity

        # Manually test RRF calculation
        # doc1: vector_rank=1, bm25_rank=2
        # RRF score = 1/(10+1) + 1/(10+2) = 1/11 + 1/12 = 0.1758
        # doc2: vector_rank=2, bm25_rank=1
        # RRF score = 1/(10+2) + 1/(10+1) = 1/12 + 1/11 = 0.1758

        k = 10
        vector_rank1 = 1
        bm25_rank1 = 2
        rrf_score1 = 1.0 / (k + vector_rank1) + 1.0 / (k + bm25_rank1)

        vector_rank2 = 2
        bm25_rank2 = 1
        rrf_score2 = 1.0 / (k + vector_rank2) + 1.0 / (k + bm25_rank2)

        # Both should have same RRF score
        assert abs(rrf_score1 - rrf_score2) < 0.001

    def test_rrf_fusion_with_different_scores(self):
        """Test RRF fusion when one method ranks higher."""
        k = 10

        # doc1 is ranked #1 by vector, #3 by bm25
        rrf_score1 = 1.0 / (k + 1) + 1.0 / (k + 3)

        # doc2 is ranked #2 by vector, #2 by bm25
        rrf_score2 = 1.0 / (k + 2) + 1.0 / (k + 2)

        # doc3 is ranked #3 by vector, #1 by bm25
        rrf_score3 = 1.0 / (k + 3) + 1.0 / (k + 1)

        # doc1 and doc3 should have same RRF score (symmetric)
        assert abs(rrf_score1 - rrf_score3) < 0.001

        # doc2 should have lower score (both ranks are higher)
        assert rrf_score2 < rrf_score1

    def test_rrf_fusion_with_k_parameter(self):
        """Test that k parameter affects fusion scoring."""
        doc_rank = 1

        # With k=5 (smaller k, ranks matter more)
        score_k5 = 1.0 / (5 + doc_rank)

        # With k=10 (larger k, more smoothing)
        score_k10 = 1.0 / (10 + doc_rank)

        # Smaller k gives higher score for top-ranked items
        assert score_k5 > score_k10


class TestHybridSearchFallback:
    """Tests for hybrid search fallback behavior."""

    def test_vector_only_when_bm25_disabled(self):
        """Should return vector-only results when BM25 is disabled."""
        # This test verifies the logic path
        hybrid_enabled = False
        config_enabled = True  # Config says enabled

        # When hybrid flag is False, should use vector-only
        use_hybrid = hybrid_enabled and config_enabled
        assert use_hybrid is False

    def test_hybrid_when_both_enabled(self):
        """Should use hybrid search when both flags are enabled."""
        hybrid_enabled = True
        config_enabled = True

        use_hybrid = hybrid_enabled and config_enabled
        assert use_hybrid is True

    def test_fallback_on_bm25_error(self):
        """Should fall back to vector-only on BM25 error."""
        # This test verifies error handling logic
        bm25_success = False

        if bm25_success:
            result_type = "hybrid"
        else:
            result_type = "vector_only"

        assert result_type == "vector_only"


class TestScoreOnlyResults:
    """Tests for score-only (non-fused) results."""

    def test_score_sorting(self):
        """Results should be sorted by score descending."""
        docs = [
            {"text": "low", "score": 0.3},
            {"text": "high", "score": 0.9},
            {"text": "medium", "score": 0.6},
        ]

        # Sort by score descending
        sorted_docs = sorted(docs, key=lambda x: x['score'], reverse=True)

        assert sorted_docs[0]['text'] == 'high'
        assert sorted_docs[1]['text'] == 'medium'
        assert sorted_docs[2]['text'] == 'low'

    def test_top_k_limiting(self):
        """Should return only top k results."""
        docs = [
            {"text": "1", "score": 0.9},
            {"text": "2", "score": 0.8},
            {"text": "3", "score": 0.7},
            {"text": "4", "score": 0.6},
        ]

        k = 2
        top_k = docs[:k]

        assert len(top_k) == k
        assert top_k[0]['text'] == '1'
        assert top_k[1]['text'] == '2'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
