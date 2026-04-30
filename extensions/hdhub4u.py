import json
import re
import urllib.parse
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    SearchQuality
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor, get_manager
from cloudstream_cli.utils import get_redirect_links, fix_url

class HDhub4uProvider(MainAPI):
    name: str = "HDHub4U"
    main_url: str = "https://hdhub4u.rehab"
    lang: str = "hi"
    supported_types = {TvType.Movie, TvType.TvSeries, TvType.Anime}
    
    TMDB_API = "https://wild-surf-4a0d.phisher1.workers.dev"
    TMDB_API_KEY = "1865f43a0549ca50d341dd9ab8b29f49"
    TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
    
    DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
            "Cookie": "xla=s4t"
        }
        self.cached_domains = None

    async def _get_domains(self):
        if self.cached_domains: return self.cached_domains
        try:
            resp = await self._session.get(self.DOMAINS_URL)
            if resp.status_code == 200:
                self.cached_domains = resp.json()
                if "HDHUB4u" in self.cached_domains:
                    self.main_url = self.cached_domains["HDHUB4u"]
            return self.cached_domains
        except: return None

    def _get_search_quality(self, check: str) -> Optional[SearchQuality]:
        if not check: return None
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
        await self._get_domains()
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
        if resp.status_code != 200: return None
        data = resp.json()
        results = []
        for hit in data.get("hits", []):
            doc = hit.get("document", {})
            results.append(MovieSearchResponse(
                name=doc.get("post_title"),
                url=doc.get("permalink"),
                apiName=self.name,
                type=TvType.Movie,
                posterUrl=doc.get("post_thumbnail"),
                quality=self._get_search_quality(doc.get("post_title"))
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        await self._get_domains()
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200: return None
        parser = self._session.parse_html(resp.text)
        
        title_raw = parser.css_first("h1.page-title span")
        title = title_raw.text() if title_raw else "Unknown"
        
        poster_el = parser.css_first("main.page-body img.aligncenter")
        poster = poster_el.attributes.get("src") if poster_el else None
        
        plot_el = parser.css_first(".kno-rdesc .kno-rdesc")
        plot = plot_el.text() if plot_el else None
        
        typeraw = parser.css_first("h1.page-title span").text() if title_raw else ""
        tv_type = TvType.Movie if "movie" in typeraw.lower() else TvType.TvSeries
        
        trailer_el = parser.css_first(".responsive-embed-container iframe")
        trailer = trailer_el.attributes.get("src", "").replace("/embed/", "/watch?v=") if trailer_el else None
        
        # Determine TMDB ID from page
        tmdb_id = None
        tmdb_a = parser.css_first("div span a[href*='themoviedb.org']")
        if tmdb_a:
            href = tmdb_a.attributes.get("href", "")
            match = re.search(r"/(\d+)", href)
            if match: tmdb_id = match.group(1)

        tmdb_data = {}
        if tmdb_id:
            m_type = "movie" if tv_type == TvType.Movie else "tv"
            tmdb_url = f"{self.TMDB_API}/{m_type}/{tmdb_id}?api_key={self.TMDB_API_KEY}&append_to_response=credits"
            tmdb_resp = await self._session.get(tmdb_url, headers=self.headers)
            if tmdb_resp.status_code == 200:
                tmdb_data = tmdb_resp.json()

        fixed_title = tmdb_data.get("title") or tmdb_data.get("name") or title
        fixed_poster = f"{self.TMDB_IMAGE_BASE}{tmdb_data.get('poster_path')}" if tmdb_data.get("poster_path") else poster
        fixed_plot = tmdb_data.get("overview") or plot
        
        actors = []
        if "credits" in tmdb_data:
            for cast in tmdb_data["credits"].get("cast", [])[:20]:
                name = cast.get("name") or cast.get("original_name")
                if not name: continue
                profile = f"{self.TMDB_IMAGE_BASE}{cast.get('profile_path')}" if cast.get("profile_path") else None
                actors.append(ActorData(Actor(name, profile), roleString=cast.get("character")))

        if tv_type == TvType.Movie:
            links = []
            for a in parser.css("h3 a, h4 a"):
                text = a.text()
                if any(q in text for q in ["480p", "720p", "1080p", "2160p", "4K"]):
                    links.append(a.attributes.get("href"))
            
            # extractLinksATags from Kotlin
            allowed_domains = re.compile(r"https://(.*\.)?(hdstream4u|hubstream)\..*")
            for a in parser.css(".page-body > div a"):
                href = a.attributes.get("href", "")
                if allowed_domains.match(href):
                    links.append(href)
                    
            return MovieLoadResponse(
                name=fixed_title, url=url, apiName=self.name, type=TvType.Movie,
                dataUrl=json.dumps(list(set(links))), posterUrl=fixed_poster, plot=fixed_plot,
                actors=actors, tags=[t.text() for t in parser.css(".page-meta em")]
            )
        else:
            # Series logic
            episodes = []
            ep_links_map = {}
            
            # Simple version of series parsing
            for element in parser.css("h3, h4"):
                text = element.text()
                ep_match = re.search(r"EPiSODE\s*(\d+)", text, re.I)
                ep_num = int(ep_match.group(1)) if ep_match else None
                
                if ep_num:
                    links = [a.attributes.get("href") for a in element.css("a[href]")]
                    if ep_num not in ep_links_map: ep_links_map[ep_num] = []
                    ep_links_map[ep_num].extend(links)

            for ep_num, links in sorted(ep_links_map.items()):
                episodes.append(Episode(name=f"Episode {ep_num}", episode=ep_num, data=json.dumps(list(set(links)))))
                
            return TvSeriesLoadResponse(
                name=fixed_title, url=url, apiName=self.name, type=TvType.TvSeries,
                posterUrl=fixed_poster, plot=fixed_plot, episodes=episodes,
                actors=actors, tags=[t.text() for t in parser.css(".page-meta em")]
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
            if not link: continue
            resolved = link
            if "id=" in link:
                resolved = await get_redirect_links(link, self._session)
            
            if await load_extractor(resolved, self.main_url, callback, subtitle_callback):
                found = True
        return found
