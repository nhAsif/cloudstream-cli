import json
import re
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    SearchQuality
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor

class HDhub4uProvider(MainAPI):
    name: str = "HDHub4U"
    main_url: str = "https://hdhub4u.rehab" # Default, might change
    lang: str = "hi"
    supported_types = {TvType.Movie, TvType.TvSeries, TvType.Anime}

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "Cookie": "xla=s4t"
        }

    def _get_search_quality(self, check: str) -> Optional[SearchQuality]:
        if not check:
            return None
        s = check.lower()
        if any(x in s for x in ["4k", "uhd", "2160p"]): return SearchQuality.FourK
        if any(x in s for x in ["hdts", "hdcam", "hdtc"]): return SearchQuality.HdCam
        if any(x in s for x in ["camrip", "cam-rip"]): return SearchQuality.CamRip
        if "cam" in s: return SearchQuality.Cam
        if any(x in s for x in ["web-dl", "webrip", "webdl"]): return SearchQuality.WebRip
        if any(x in s for x in ["bluray", "bdrip", "blu-ray"]): return SearchQuality.BlueRay
        if "1080p" in s: return SearchQuality.HD
        if "720p" in s: return SearchQuality.SD
        return None

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        # Using the search API identified in the Kotlin source
        url = "https://search.pingora.fyi/collections/post/documents/search"
        params = {
            "q": query,
            "query_by": "post_title,category",
            "query_by_weights": "4,2",
            "sort_by": "sort_by_date:desc",
            "limit": "15",
            "highlight_fields": "none",
            "use_cache": "true",
            "page": page
        }
        resp = await self._session.get(url, params=params, headers=self.headers, referer=self.main_url)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        results = []
        for hit in data.get("hits", []):
            doc = hit.get("document", {})
            results.append(SearchResponse(
                name=doc.get("post_title"),
                url=doc.get("permalink"),
                apiName=self.name,
                type=TvType.Movie, # Default to movie, can be refined
                posterUrl=doc.get("post_thumbnail")
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        
        # Simplified parsing logic based on Kotlin source
        title = parser.css_first("h1.page-title span")
        title_text = title.text() if title else "Unknown"
        
        poster = parser.css_first("main.page-body img.aligncenter")
        poster_url = poster.attributes.get("src") if poster else None
        
        plot = parser.css_first(".kno-rdesc .kno-rdesc")
        plot_text = plot.text() if plot else None
        
        is_movie = "movie" in title_text.lower()
        
        # In HDhub4u, links are often hidden in buttons/A tags with specific qualities
        links = []
        for a in parser.css("h3 a, h4 a"):
            href = a.attributes.get("href")
            text = a.text()
            if href and any(q in text for q in ["480p", "720p", "1080p", "2160p", "4K"]):
                links.append(href)
        
        if is_movie:
            return MovieLoadResponse(
                name=title_text,
                url=url,
                apiName=self.name,
                type=TvType.Movie,
                dataUrl=json.dumps(links),
                posterUrl=poster_url,
                plot=plot_text
            )
        else:
            # Handle episodes - simplified for now
            episodes = []
            # Logic for parsing episodes would go here
            return TvSeriesLoadResponse(
                name=title_text,
                url=url,
                apiName=self.name,
                type=TvType.TvSeries,
                dataUrl=json.dumps(links),
                posterUrl=poster_url,
                plot=plot_text,
                episodes=episodes
            )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        try:
            links = json.loads(data)
        except:
            links = [data]
            
        found = False
        for link in links:
            # Recursively resolve using load_extractor
            if await load_extractor(link, self.main_url, callback, subtitle_callback):
                found = True
        return found
