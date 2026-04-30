from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Set
from .models import TvType, SearchResponse, LoadResponse, ExtractorLink, SubtitleFile, HomePageResponse, MainPageRequest

class MainAPI(ABC):
    """
    Abstract base class for content providers.
    """
    name: str = "NONE"
    main_url: str = "NONE"
    lang: str = "en"
    has_main_page: bool = False
    supported_types: Set[TvType] = {
        TvType.Movie,
        TvType.TvSeries,
        TvType.Cartoon,
        TvType.Anime,
        TvType.OVA,
    }

    @abstractmethod
    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        """
        Search for content using the provider.
        
        :param query: The search query string.
        :param page: The page number for paginated results (starts at 1).
        :return: A list of SearchResponse objects or None if the search failed.
        """
        pass

    async def getMainPage(self, page: int = 1, request: Optional[MainPageRequest] = None) -> Optional[HomePageResponse]:
        """
        Get the main page content for the provider.
        
        :param page: The page number.
        :param request: Optional MainPageRequest.
        :return: A HomePageResponse object or None.
        """
        return None

    @abstractmethod
    async def load(self, url: str) -> Optional[LoadResponse]:
        """
        Load detailed information about a specific piece of content.
        
        :param url: The URL of the content to load.
        :return: A LoadResponse object or None if loading failed.
        """
        pass

    @abstractmethod
    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        """
        Load playable links for a piece of content.
        
        :param data: The data string (usually a URL or JSON) from load().
        :param callback: A callback function to handle each found ExtractorLink.
        :param subtitle_callback: A callback function to handle each found SubtitleFile.
        :return: True if links were successfully loaded, False otherwise.
        """
        pass

class ExtractorApi(ABC):
    """
    Abstract base class for video link extractors.
    """
    name: str
    main_url: str

    @abstractmethod
    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        """
        Extract direct video links from a URL.
        
        :param url: The URL to extract links from.
        :param referer: An optional referer URL.
        :param callback: A callback function to handle each found ExtractorLink.
        :param subtitle_callback: A callback function to handle each found SubtitleFile.
        """
        pass
