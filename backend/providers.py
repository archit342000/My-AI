"""Provider/Factory patterns for shared resources.

This module provides formalized providers for accessing shared infrastructure
like the RAGManager singleton. This ensures proper configuration and prevents
direct instantiation that could bypass central management.
"""

from backend.rag import RAGManager


class RAGProvider:
    """Provider for RAGManager singleton access.

    This class enforces the singleton pattern for RAGManager by:
    1. Only allowing initialization through get_manager()
    2. Blocking direct instantiation of RAGManager
    3. Ensuring all code shares the same configured instance

    Config is set on the first call to get_manager(). Subsequent calls
    return the same instance regardless of config parameters passed.
    """

    _rag_manager = None
    _initialized = False
    _config = {}

    @classmethod
    def get_manager(
        cls,
        persist_path,
        api_url,
        embedding_model,
        api_key
    ) -> RAGManager:
        """Get the RAGManager singleton instance.

        Args:
            persist_path: Path to ChromaDB data directory (only used on first call)
            api_url: URL for embedding API (only used on first call)
            embedding_model: Model name for embeddings (only used on first call)
            api_key: API key for embedding service (only used on first call)

        Returns:
            The RAGManager singleton instance

        Raises:
            RuntimeError: If RAGManager instantiation fails
        """
        if cls._initialized:
            # Return existing instance, ignoring config parameters
            return cls._rag_manager

        # First call: initialize with provided config
        # Use object.__new__ to bypass RAGManager's blocked __new__
        try:
            rag_manager = object.__new__(RAGManager)
            # Manually set up the singleton state
            RAGManager._instance = rag_manager
            RAGManager._initialized = False  # Will be set to True after init

            # Authorize initialization for the provider
            rag_manager._authorized_initialization = True

            rag_manager.__init__(
                persist_path=persist_path,
                api_url=api_url,
                embedding_model=embedding_model,
                api_key=api_key
            )
            cls._rag_manager = rag_manager
            cls._initialized = True
            cls._config = {
                'persist_path': persist_path,
                'api_url': api_url,
                'embedding_model': embedding_model,
                'api_key': api_key
            }
            return cls._rag_manager
        except Exception as e:
            raise RuntimeError(f"Failed to initialize RAGManager via RAGProvider: {e}")

    @classmethod
    def reset(cls):
        """Reset the provider state (useful for testing).

        This allows re-initialization on the next get_manager() call.
        """
        cls._rag_manager = None
        cls._initialized = False
        cls._config = {}
        RAGManager._instance = None
        RAGManager._initialized = False

    @classmethod
    def get_config(cls) -> dict:
        """Get the configuration used to initialize the provider.

        Returns:
            Dict of config values, or empty dict if not initialized
        """
        return cls._config.copy()
