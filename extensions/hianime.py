import json
import re
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, LoadResponse, AnimeLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    DubStatus, ShowStatus
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor

class HiAnimeProvider(MainAPI):
    name: str = "HiAnime"
    main_url: str = "https://hianime.to"
    lang: str = "en"
    supported_types = {TvType.Anime, TvType.AnimeMovie, TvType.OVA}

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": self.main_url,
            "X-Requested-With": "XMLHttpRequest"
        }

    def _get_type(self, t: str) -> TvType:
        if "OVA" in t or "Special" in t:
            return TvType.OVA
        elif "Movie" in t:
            return TvType.AnimeMovie
        return TvType.Anime

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        url = f"{self.main_url}/search?keyword={query}&page={page}"
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        results = []
        for item in parser.css("div.flw-item"):
            a = item.css_first("a")
            title_node = item.css_first("h3.film-name")
            if not a or not title_node: continue
            
            href = a.attributes.get("href")
            if not href.startswith("http"):
                href = f"{self.main_url}{href}"
            
            title = title_node.text().strip()
            poster = item.css_first("img").attributes.get("data-src")
            
            results.append(SearchResponse(
                name=title,
                url=href,
                apiName=self.name,
                type=TvType.Anime,
                posterUrl=poster
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        # HiAnime URLs can be /watch/name-id or /name-id
        # The info page is usually the one without /watch/
        info_url = url.replace("/watch/", "/")
        resp = await self._session.get(info_url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        
        title = parser.css_first(".anisc-detail .film-name").text().strip()
        plot = parser.css_first(".film-description .text").text().strip() if parser.css_first(".film-description .text") else None
        poster = parser.css_first(".film-poster img").attributes.get("src")
        
        # Get anime ID from the URL or a sync data element
        anime_id = url.split("-")[-1]
        
        # Fetch episode list via AJAX
        ep_resp = await self._session.get(f"{self.main_url}/ajax/v2/episode/list/{anime_id}", headers=self.headers)
        episodes = []
        if ep_resp.status_code == 200:
            ep_data = ep_resp.json()
            if ep_data.get("status"):
                ep_parser = self._session.parse_html(ep_data.get("html", ""))
                for ep_item in ep_parser.css(".ss-list a"):
                    ep_id = ep_item.attributes.get("data-id")
                    ep_num_node = ep_item.css_first(".ssli-order")
                    ep_num = int(ep_num_node.text()) if ep_num_node else 0
                    ep_name = ep_item.attributes.get("title")
                    
                    # Store both sub and dub data in the episode data string
                    episodes.append(Episode(
                        data=json.dumps({"id": ep_id, "num": ep_num}),
                        name=ep_name,
                        episode=ep_num
                    ))
        
        return AnimeLoadResponse(
            name=title,
            url=url,
            apiName=self.name,
            type=TvType.Anime,
            dataUrl=url,
            posterUrl=poster,
            plot=plot,
            episodes={DubStatus.Subbed: episodes} # Simplified for CLI
        )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        try:
            ep_info = json.loads(data)
            ep_id = ep_info.get("id")
        except:
            # Fallback if it's just a raw ID or URL
            ep_id = data.split("ep=")[-1] if "ep=" in data else data
            
        # 1. Get available servers for this episode
        servers_resp = await self._session.get(
            f"{self.main_url}/ajax/v2/episode/servers?episodeId={ep_id}",
            headers=self.headers
        )
        if servers_resp.status_code != 200:
            return False
            
        servers_data = servers_resp.json()
        if not servers_data.get("status"):
            return False
            
        server_parser = self._session.parse_html(servers_data.get("html", ""))
        found = False
        
        # 2. Iterate through servers and get sources
        for server_item in server_parser.css(".server-item"):
            server_id = server_item.attributes.get("data-id")
            server_name = server_item.text().strip()
            
            source_resp = await self._session.get(
                f"{self.main_url}/ajax/v2/episode/sources?id={server_id}",
                headers=self.headers
            )
            if source_resp.status_code == 200:
                source_data = source_resp.json()
                source_link = source_data.get("link")
                if source_link:
                    # 3. Resolve using the orchestrator's load_extractor
                    if await load_extractor(source_link, self.main_url, callback, subtitle_callback):
                        found = True
        
        return found
