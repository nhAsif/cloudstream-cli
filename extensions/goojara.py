import re
from typing import List, Optional, Callable, Dict
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor

class GoojaraProvider(MainAPI):
    name: str = "Goojara"
    main_url: str = "https://www.goojara.to"
    lang: str = "en"
    supported_types = {TvType.Movie, TvType.TvSeries}

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        url = f"{self.main_url}/xsearch.php"
        data = {"q": query}
        resp = await self._session.post(url, data=data, referer=self.main_url)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        results = []
        for item in parser.css("ul.lites li"):
            a = item.css_first("a")
            if not a: continue
            
            title = a.text().strip()
            href = a.attributes.get("href")
            
            results.append(SearchResponse(
                name=title,
                url=href,
                apiName=self.name,
                type=TvType.Movie # Goojara search is mixed
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        resp = await self._session.get(url)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        
        title = parser.css_first("h1").text().strip()
        plot = parser.css_first(".finfo").text().strip() if parser.css_first(".finfo") else None
        poster = parser.css_first(".mvic-thumb img").attributes.get("src") if parser.css_first(".mvic-thumb img") else None
        
        # Simplified: check for episode list
        is_tv = parser.css_first("#seasons") is not None
        
        if not is_tv:
            return MovieLoadResponse(
                name=title,
                url=url,
                apiName=self.name,
                type=TvType.Movie,
                dataUrl=url, # Goojara often embeds directly or uses a secondary page
                posterUrl=poster,
                plot=plot
            )
        else:
            episodes = []
            # Logic for parsing Goojara seasons/episodes would go here
            return TvSeriesLoadResponse(
                name=title,
                url=url,
                apiName=self.name,
                type=TvType.TvSeries,
                dataUrl=url,
                posterUrl=poster,
                plot=plot,
                episodes=episodes
            )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        # Goojara uses a specific redirect/iframe system.
        # This is a simplified placeholder for the actual extraction logic.
        resp = await self._session.get(data)
        # Find iframes or specific video links...
        # For now, we'll try to load extractors for any links found
        return await load_extractor(data, self.main_url, callback, subtitle_callback)
