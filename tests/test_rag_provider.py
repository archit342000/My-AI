"""Tests for RAGProvider singleton enforcement.

Tests that verify:
1. Direct RAGManager() instantiation raises RuntimeError
2. RAGProvider.get_manager() returns singleton instance
3. Config is set on first call; subsequent calls ignore parameters
"""

import pytest


class TestRAGManagerBlock:
    """Tests that RAGManager blocks direct instantiation."""

    def test_direct_instantiation_raises_runtime_error(self):
        """Direct RAGManager() should raise RuntimeError."""
        from backend.rag import RAGManager

        with pytest.raises(RuntimeError) as exc_info:
            RAGManager()

        assert "RAGManager must be accessed via RAGProvider.get_manager()" in str(exc_info.value)

    def test_direct_instantiation_with_params_raises_runtime_error(self):
        """Direct RAGManager(persist_path=...) should also raise RuntimeError."""
        from backend.rag import RAGManager

        with pytest.raises(RuntimeError) as exc_info:
            RAGManager(persist_path="/tmp/test")

        assert "RAGManager must be accessed via RAGProvider.get_manager()" in str(exc_info.value)


class TestRAGProvider:
    """Tests for RAGProvider singleton access."""

    def test_get_manager_returns_instance(self, temp_config):
        """RAGProvider.get_manager() should return a RAGManager instance."""
        from backend.providers import RAGProvider
        from backend.rag import RAGManager

        manager = RAGProvider.get_manager(**temp_config)
        assert isinstance(manager, RAGManager)

    def test_get_manager_returns_same_instance(self, temp_config):
        """Multiple get_manager() calls should return the same instance."""
        from backend.providers import RAGProvider

        manager1 = RAGProvider.get_manager(**temp_config)
        manager2 = RAGProvider.get_manager(**temp_config)

        assert manager1 is manager2

    def test_get_manager_ignores_config_on_subsequent_calls(self, temp_config):
        """Subsequent calls with different config should not reinitialize."""
        from backend.providers import RAGProvider

        manager1 = RAGProvider.get_manager(**temp_config)

        # Try with different config - should still return same instance
        different_config = temp_config.copy()
        different_config['persist_path'] = '/different/path'

        manager2 = RAGProvider.get_manager(**different_config)

        assert manager1 is manager2
        # Config should be from first call
        assert RAGProvider.get_config()['persist_path'] == temp_config['persist_path']

    def test_reset_allows_reinitialization(self, temp_config):
        """reset() should allow reinitialization on next get_manager() call."""
        from backend.providers import RAGProvider

        manager1 = RAGProvider.get_manager(**temp_config)
        RAGProvider.reset()

        manager2 = RAGProvider.get_manager(**temp_config)

        assert manager1 is not manager2

    def test_get_config_returns_config(self, temp_config):
        """get_config() should return the initialization config."""
        from backend.providers import RAGProvider

        RAGProvider.reset()
        RAGProvider.get_manager(**temp_config)

        config = RAGProvider.get_config()
        assert config['persist_path'] == temp_config['persist_path']
        assert config['api_url'] == temp_config['api_url']
        assert config['embedding_model'] == temp_config['embedding_model']
