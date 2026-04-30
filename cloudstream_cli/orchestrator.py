import asyncio
import re
from typing import List, Optional, Callable, Dict, Union
from .base import MainAPI, ExtractorApi
from .models import SearchResponse, LoadResponse, ExtractorLink, SubtitleFile
from .network import Session

class ProviderManager:
    """
    Manages registration and orchestration of content providers and link extractors.
    """
    def __init__(self, session: Optional[Session] = None):
        self.providers: Dict[str, MainAPI] = {}
        self.extractors: List[ExtractorApi] = []
        self._session = session

    @property
    def session(self) -> Session:
        """
        Get the session instance, creating one if it doesn't exist.
        """
        if self._session is None:
            self._session = Session()
        return self._session

    def register_provider(self, provider: MainAPI):
        """
        Register a MainAPI provider instance.
        """
        self.providers[provider.name] = provider

    def register_extractor(self, extractor: ExtractorApi):
        """
        Register an ExtractorApi instance.
        """
        self.extractors.append(extractor)

    async def search(
        self, 
        query: str, 
        providers: Optional[List[str]] = None
    ) -> List[SearchResponse]:
        """
        Search for content across specified (or all) registered providers in parallel.
        """
        target_providers = []
        if providers:
            for name in providers:
                if name in self.providers:
                    target_providers.append(self.providers[name])
        else:
            target_providers = list(self.providers.values())

        if not target_providers:
            return []

        # Parallel search using asyncio.gather
        tasks = [provider.search(query) for provider in target_providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        for res in results:
            if isinstance(res, list):
                all_results.extend(res)
            # Exceptions are ignored for now, but could be logged or handled
        return all_results

    async def load(self, url: str) -> Optional[LoadResponse]:
        """
        Identify the correct provider based on the URL and call its load method.
        """
        for provider in self.providers.values():
            # Simple prefix check, matching Kotlin's getApiFromUrlNull logic
            if url.startswith(provider.main_url):
                return await provider.load(url)
        return None

    async def load_extractor(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        """
        Port of ExtractorApi.kt's loadExtractor logic.
        Matches a URL against registered extractors and runs them.
        """
        # Schema stripping for comparison, ported from schemaStripRegex in Kotlin
        def strip_schema(u: str):
            return re.sub(r'^(https?:|)//(www\.)?', '', u)

        # Note: unshortenLinkSafe logic is omitted as it depends on ShortLink utilities
        current_url = url
        compare_url = strip_schema(current_url.lower())
        
        # Iterate in reverse order so newer registered extractors take priority
        for extractor in reversed(self.extractors):
            extractor_url_stripped = strip_schema(extractor.main_url.lower())
            
            # Check for exact prefix match or if the domain is contained in the URL
            if compare_url.startswith(extractor_url_stripped) or extractor_url_stripped in compare_url:
                try:
                    await extractor.get_url(
                        current_url, 
                        referer, 
                        callback, 
                        subtitle_callback
                    )
                    return True
                except Exception:
                    # In Kotlin, errors are logged but execution continues for other extractors if any
                    pass
        
        # Fuzzy matching (ratio > 80) is omitted as it requires fuzzywuzzy dependency
        
        return False

    async def resolve_links(
        self,
        url: str,
        provider_name: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        """
        Orchestrate link resolution using a provider and available extractors.
        Uses the provider to get initial data and manages the extraction process.
        """
        provider = self.providers.get(provider_name)
        if not provider:
            return False

        # The orchestrator manages the extraction process.
        # This implementation calls the provider's load_links which is expected 
        # to either provide direct links or call load_extractor recursively.
        return await provider.load_links(url, callback, subtitle_callback)

# Singleton-like access for global utility functions
_default_manager: Optional[ProviderManager] = None

def get_manager() -> ProviderManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ProviderManager()
        # Register default extractors
        try:
            from .extractors import get_extractors
            for extractor in get_extractors():
                _default_manager.register_extractor(extractor)
        except ImportError:
            pass
        
        # Register default providers
        try:
            from .providers import get_providers
            for provider in get_providers(_default_manager.session):
                _default_manager.register_provider(provider)
        except ImportError:
            pass
        
        # Load external extensions
        try:
            from .extensions import load_all_extensions
            load_all_extensions(_default_manager)
        except ImportError:
            pass
            
    return _default_manager

async def load_extractor(
    url: str,
    referer: Optional[str],
    callback: Callable[[ExtractorLink], None],
    subtitle_callback: Callable[[SubtitleFile], None]
) -> bool:
    """
    Global utility function for link extraction, matching Kotlin's top-level loadExtractor.
    """
    return await get_manager().load_extractor(url, referer, callback, subtitle_callback)
