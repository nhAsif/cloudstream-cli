import json
import re
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    SearchQuality
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor

class TamilblastersProvider(MainAPI):
    name: str = "Tamilblasters"
    main_url: str = "https://www.1tamilblasters.company/"
    lang: str = "ta"
    supported_types = {TvType.Movie, TvType.TvSeries}

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.streamhg = "https://cavanhabg.com"

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        url = f"{self.main_url}/?s={query}"
        resp = await self._session.get(url)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        results = []
        for item in parser.css("div.article-content-col"):
            a = item.css_first("h2 a")
            if not a: continue
            
            title = a.text().strip()
            href = a.attributes.get("href")
            img = item.css_first("img")
            poster = img.attributes.get("src") if img else None
            
            results.append(SearchResponse(
                name=title,
                url=href,
                apiName=self.name,
                type=TvType.Movie,
                posterUrl=poster
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        resp = await self._session.get(url)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        
        og_desc_meta = parser.css_first("meta[property='og:description']")
        if not og_desc_meta: return None
        og_desc = og_desc_meta.attributes.get("content", "")
        
        # Name: Movie Name (Year)
        title = og_desc.split("Name:")[1].split("(")[0].strip() if "Name:" in og_desc else "Unknown"
        year_match = re.search(r"\((\d{4})\)", og_desc)
        year = int(year_match.group(1)) if year_match else None
        
        is_tv = og_desc.lower().startswith("tv series") or "season" in og_desc.lower()
        
        poster_meta = parser.css_first("meta[property='og:image']")
        poster = poster_meta.attributes.get("content") if poster_meta else None
        
        plot_node = parser.css_first("p:has(strong)") # This might need more complex logic
        # For simplicity, we'll just take some text
        plot = "No plot available."
        
        if not is_tv:
            return MovieLoadResponse(
                name=title,
                url=url,
                apiName=self.name,
                type=TvType.Movie,
                dataUrl=url,
                posterUrl=poster,
                year=year,
                plot=plot
            )
        else:
            episodes = []
            # Extract iframes as episodes
            for idx, iframe in enumerate(parser.css("iframe")):
                src = iframe.attributes.get("src")
                if src:
                    # Try to find a label
                    episodes.append(Episode(
                        data=json.dumps({"title": f"Episode {idx+1}", "url": src}),
                        name=f"Episode {idx+1}",
                        episode=idx+1
                    ))
            
            return TvSeriesLoadResponse(
                name=title,
                url=url,
                apiName=self.name,
                type=TvType.TvSeries,
                dataUrl=url,
                posterUrl=poster,
                year=year,
                plot=plot,
                episodes=episodes
            )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        if data.startswith("{"):
            try:
                load_data = json.loads(data)
                url = load_data.get("url")
                if "hg" in url:
                    # Fix HGcloud URLs
                    if "/e/" in url:
                        url = f"{self.streamhg}/e/{url.split('/e/')[1]}"
                return await load_extractor(url, self.main_url, callback, subtitle_callback)
            except:
                return False
        else:
            # It's the main page URL, parse for iframes
            resp = await self._session.get(data)
            parser = self._session.parse_html(resp.text)
            found = False
            for iframe in parser.css("iframe"):
                src = iframe.attributes.get("src")
                if src:
                    if await load_extractor(src, self.main_url, callback, subtitle_callback):
                        found = True
            return found
