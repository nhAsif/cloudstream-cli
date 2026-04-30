import json
import re
import urllib.parse
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    SearchQuality, Score
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor, get_manager
from cloudstream_cli.utils import fix_url

class BanglaplexProvider(MainAPI):
    name: str = "Banglaplex"
    main_url: str = "https://banglaplex.click"
    lang: str = "bn"
    supported_types = {TvType.Movie, TvType.TvSeries}
    
    DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        self.cached_domains = None

    async def _get_domains(self):
        if self.cached_domains: return self.cached_domains
        try:
            resp = await self._session.get(self.DOMAINS_URL)
            if resp.status_code == 200:
                self.cached_domains = resp.json()
                if "banglaplex" in self.cached_domains:
                    self.main_url = self.cached_domains["banglaplex"]
            return self.cached_domains
        except: return None

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        await self._get_domains()
        if page == 1:
            url = f"{self.main_url}/search?q={urllib.parse.quote(query)}"
        else:
            url = f"{self.main_url}/search?q={urllib.parse.quote(query)}&per_page={page * 12}"
            
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200: return None
        
        parser = self._session.parse_html(resp.text)
        results = []
        for card in parser.css("div.movie-container > div.col-md-2"):
            title_a = card.css_first("div.movie-img > div.movie-title > h3 > a")
            if not title_a: continue
            title = title_a.text().strip()
            href = fix_url(title_a.attributes.get("href"), self.main_url)
            
            img_container = card.css_first("div > div.latest-movie-img-container")
            poster = ""
            if img_container:
                style = img_container.attributes.get("style", "")
                match = re.search(r"url\('([^']+)'\)", style)
                if match: poster = fix_url(match.group(1), self.main_url)
            
            quality_text = card.css_first("span.label.label-primary").text() if card.css_first("span.label.label-primary") else ""
            score_el = card.css_first("span.label.label-imdb")
            score_val = score_el.text().replace("IMDB", "").strip() if score_el else None
            
            results.append(MovieSearchResponse(
                name=title, url=href, apiName=self.name, type=TvType.Movie,
                posterUrl=poster, quality=self._get_quality(quality_text),
                score=int(float(score_val)*10) if score_val else None
            ))
        return results

    def _get_quality(self, q: str) -> SearchQuality:
        q = q.lower()
        if "4k" in q: return SearchQuality.FourK
        if "720" in q: return SearchQuality.SD
        if "1080" in q: return SearchQuality.HD
        return SearchQuality.HD

    async def load(self, url: str) -> Optional[LoadResponse]:
        await self._get_domains()
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200: return None
        parser = self._session.parse_html(resp.text)
        
        title_el = parser.css_first("meta[property='og:title']")
        title = title_el.attributes.get("content", "").replace(" | Watch Online", "").strip() if title_el else "Unknown"
        
        poster_el = parser.css_first("#info > div > div > img")
        poster = poster_el.attributes.get("src") if poster_el else None
        
        desc_el = parser.css_first("meta[property='og:description']")
        plot = desc_el.attributes.get("content", "").strip() if desc_el else None
        
        return MovieLoadResponse(
            name=title, url=url, apiName=self.name, type=TvType.Movie,
            dataUrl=url, posterUrl=poster, plot=plot
        )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        resp = await self._session.get(data, headers=self.headers)
        if resp.status_code != 200: return False
        parser = self._session.parse_html(resp.text)
        
        iframe = parser.css_first("div.video-embed-container > iframe")
        if iframe:
            src = iframe.attributes.get("src")
            if src: await load_extractor(src, self.main_url, callback, subtitle_callback)
            
        download_a = parser.css_first("#download a")
        if download_a:
            download_url = download_a.attributes.get("href")
            if download_url:
                token_resp = await self._session.get(download_url)
                token_parser = self._session.parse_html(token_resp.text)
                csrf_input = token_parser.css_first("form input")
                if csrf_input:
                    name = csrf_input.attributes.get("name")
                    value = csrf_input.attributes.get("value") or name
                    post_resp = await self._session.post(download_url, data={name: value})
                    post_parser = self._session.parse_html(post_resp.text)
                    for a in post_parser.css("div.row > div.col-sm-8 > a"):
                        href = a.attributes.get("href")
                        if href: await load_extractor(href, download_url, callback, subtitle_callback)
        return True
