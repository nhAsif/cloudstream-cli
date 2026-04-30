import base64
import json
import re
import urllib.parse
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, ExtractorLink, SubtitleFile,
    SearchQuality
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor, get_manager
from cloudstream_cli.utils import get_redirect_links

class FourKHDHubProvider(MainAPI):
    name: str = "4K HDHUB"
    main_url: str = "https://4khdhub.dad"
    lang: str = "en"
    supported_types = {TvType.Movie, TvType.Anime, TvType.TvSeries}
    
    TMDB_API = "https://api.themoviedb.org/3"
    TMDB_API_KEY = "e6333b32409e02a4a6eba6fb7ff866bb"
    TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"
    
    DOMAINS_URL = "https://raw.githubusercontent.com/phisher98/TVVVV/refs/heads/main/domains.json"

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session(verify=False)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        self.cached_domains = None

    async def _get_domains(self):
        if self.cached_domains:
            return self.cached_domains
        try:
            resp = await self._session.get(self.DOMAINS_URL)
            if resp.status_code == 200:
                self.cached_domains = resp.json()
                # Update mainUrl and extractor URLs
                if "4khdhub" in self.cached_domains:
                    self.main_url = self.cached_domains["4khdhub"]
                
                # Update HubCloud main_url in extractor manager
                if "hubcloud" in self.cached_domains:
                    hubcloud_url = self.cached_domains["hubcloud"]
                    manager = get_manager()
                    for extractor in manager.extractors:
                        if extractor.name == "Hub-Cloud":
                            extractor.main_url = hubcloud_url
            return self.cached_domains
        except:
            return None

    def _get_search_quality(self, tags: List[str]) -> SearchQuality:
        if not tags:
            return SearchQuality.HD
        text = " ".join(tags).lower()
        if re.search(r"\b(4k|ds4k|uhd|2160p)\b", text): return SearchQuality.FourK
        if re.search(r"\b(1440p|qhd|bluray|bdrip|blu[- ]?ray)\b", text): return SearchQuality.BlueRay
        if re.search(r"\b(1080p|fullhd|hdrip|hdtv)\b", text): return SearchQuality.HD
        if re.search(r"\b(720p)\b", text): return SearchQuality.SD
        if re.search(r"\b(web[- ]?dl|webrip|webdl)\b", text): return SearchQuality.WebRip
        if re.search(r"\b(camrip|cam[- ]?rip|rip)\b", text): return SearchQuality.CamRip
        if re.search(r"\b(hdts|hdcam|hdtc)\b", text): return SearchQuality.HdCam
        if re.search(r"\b(cam)\b", text): return SearchQuality.Cam
        if re.search(r"\b(dvd)\b", text): return SearchQuality.DVD
        if re.search(r"\b(hq)\b", text): return SearchQuality.HQ
        return SearchQuality.HD

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        await self._get_domains()
        url = f"{self.main_url}/page/{page}/?s={urllib.parse.quote(query)}"
        if page == 1:
            url = f"{self.main_url}/?s={urllib.parse.quote(query)}"
            
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        results = []
        for card in parser.css("div.card-grid a"):
            title_el = card.css_first("h3")
            if not title_el: continue
            title = title_el.text().strip()
            href = card.attributes.get("href")
            if href and not href.startswith("http"):
                href = f"{self.main_url.rstrip('/')}/{href.lstrip('/')}"
                
            img = card.css_first("img")
            poster_url = img.attributes.get("src") if img else None
            
            tags = [t.text().strip() for t in card.css("span.movie-card-format")]
            quality = self._get_search_quality(tags)
            
            results.append(MovieSearchResponse(
                name=title,
                url=href,
                apiName=self.name,
                type=TvType.Movie,
                posterUrl=poster_url,
                quality=quality
            ))
        return results

    async def _fetch_tmdb_id(self, title: str, is_movie: bool) -> Optional[int]:
        url = f"{self.TMDB_API}/search/multi?api_key={self.TMDB_API_KEY}&query={urllib.parse.quote(title.strip())}"
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        
        target_type = "movie" if is_movie else "tv"
        
        def normalize(s: Optional[str]) -> str:
            if not s: return ""
            return re.sub(r"[^a-z0-9]", "", s.lower()).strip()
        
        input_norm = normalize(title)
        fallback = None
        
        for item in results:
            if item.get("media_type") != target_type:
                continue
            
            res_title = item.get("title") if is_movie else item.get("name")
            res_norm = normalize(res_title)
            if not res_norm: continue
            
            if fallback is None:
                fallback = item.get("id")
            
            if res_norm == input_norm:
                return item.get("id")
            
            if input_norm in res_norm or res_norm in input_norm:
                return item.get("id")
                
        return fallback

    async def load(self, url: str) -> Optional[LoadResponse]:
        await self._get_domains()
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        title_raw = parser.css_first("h1.page-title")
        if not title_raw: return None
        title = title_raw.text().split("(")[0].strip()
        
        poster_el = parser.css_first("meta[property='og:image']")
        poster = poster_el.attributes.get("content") if poster_el else None
        
        # New metadata parsing
        metadata = {}
        for item in parser.css(".metadata-item"):
            label_el = item.css_first(".metadata-label")
            value_el = item.css_first(".metadata-value")
            if label_el and value_el:
                metadata[label_el.text().replace(":", "").strip()] = value_el.text().strip()

        is_movie = "Type" in metadata and "Movie" in metadata["Type"] or "Movie" in title or "movie" in url
        if not is_movie:
            tags = [t.text().strip() for t in parser.css("div.mt-2 span.badge")]
            is_movie = "Movies" in tags or "Movie" in tags

        tv_type = TvType.Movie if is_movie else TvType.TvSeries
        
        year = None
        if "Release" in metadata:
            match = re.search(r"(\d{4})", metadata["Release"])
            if match: year = int(match.group(1))
        
        if not year:
            year_el = parser.css_first("div.mt-2 span")
            if year_el:
                match = re.search(r"(\d{4})", year_el.text())
                if match: year = int(match.group(1))

        description_el = parser.css_first("div.content-section p.mt-4")
        description = description_el.text().strip() if description_el else None
        
        trailer_el = parser.css_first("#trailer-btn")
        trailer = trailer_el.attributes.get("data-trailer-url") if trailer_el else None
        
        tmdb_id = await self._fetch_tmdb_id(title, is_movie)
        
        tmdb_data = {}
        if tmdb_id:
            m_type = "movie" if is_movie else "tv"
            tmdb_url = f"{self.TMDB_API}/{m_type}/{tmdb_id}?api_key={self.TMDB_API_KEY}&append_to_response=credits"
            tmdb_resp = await self._session.get(tmdb_url, headers=self.headers)
            if tmdb_resp.status_code == 200:
                tmdb_data = tmdb_resp.json()

        fixed_title = tmdb_data.get("title") or tmdb_data.get("name") or title
        fixed_poster = f"{self.TMDB_IMAGE_BASE}{tmdb_data.get('poster_path')}" if tmdb_data.get("poster_path") else poster
        fixed_backdrop = f"{self.TMDB_IMAGE_BASE}{tmdb_data.get('backdrop_path')}" if tmdb_data.get("backdrop_path") else poster
        fixed_plot = tmdb_data.get("overview") or description
        
        tmdb_year = None
        date_str = tmdb_data.get("release_date") or tmdb_data.get("first_air_date")
        if date_str:
            try: tmdb_year = int(date_str.split("-")[0])
            except: pass
        fixed_year = tmdb_year or year
        
        rating = tmdb_data.get("vote_average")
        score = int(rating * 10) if rating and rating > 0 else None
        
        actors = []
        if "credits" in tmdb_data:
            for cast in tmdb_data["credits"].get("cast", [])[:20]:
                name = cast.get("name") or cast.get("original_name")
                if not name: continue
                profile = f"{self.TMDB_IMAGE_BASE}{cast.get('profile_path')}" if cast.get("profile_path") else None
                actors.append(ActorData(Actor(name, profile), roleString=cast.get("character")))

        recommendations = []
        for rec in parser.css("div.card-grid-small a"):
            rec_title_el = rec.css_first("h3")
            if not rec_title_el: continue
            rec_title = rec_title_el.text().strip()
            rec_href = rec.attributes.get("href")
            rec_img = rec.css_first("img")
            rec_poster = rec_img.attributes.get("src") if rec_img else None
            recommendations.append(MovieSearchResponse(rec_title, rec_href, self.name, TvType.Movie, rec_poster))

        if tv_type == TvType.TvSeries:
            episodes = []
            episodes_map = {} # (season, episode) -> List[hrefs]
            
            for season_item in parser.css("div.episodes-list div.season-item"):
                season_text = season_item.css_first("div.episode-number").text()
                season_match = re.search(r"S?(\d+)", season_text)
                if not season_match: continue
                season_num = int(season_match.group(1))
                
                for ep_item in season_item.css("div.episode-download-item"):
                    ep_badge = ep_item.css_first("div.episode-file-info span.badge-psa")
                    if not ep_badge: continue
                    ep_match = re.search(r"Episode-0*(\d+)", ep_badge.text())
                    if not ep_match: continue
                    ep_num = int(ep_match.group(1))
                    
                    hrefs = []
                    for a in ep_item.css("a"):
                        h = a.attributes.get("href")
                        if h:
                            if not h.startswith("http"):
                                h = f"{self.main_url.rstrip('/')}/{h.lstrip('/')}"
                            hrefs.append(h)
                    
                    if hrefs:
                        if tmdb_id:
                            # Add direct players
                            hrefs.append(f"https://player.videasy.net/tv/{tmdb_id}/{season_num}/{ep_num}")
                            hrefs.append(f"https://player.autoembed.cc/embed/tv/{tmdb_id}/{season_num}/{ep_num}")
                        
                        key = (season_num, ep_num)
                        if key not in episodes_map: episodes_map[key] = []
                        episodes_map[key].extend(hrefs)
            
            for (s, e), hrefs in sorted(episodes_map.items()):
                episodes.append(Episode(
                    name=f"Episode {e}",
                    season=s,
                    episode=e,
                    data=json.dumps(list(set(hrefs)))
                ))

            return TvSeriesLoadResponse(
                name=fixed_title,
                url=url,
                apiName=self.name,
                type=TvType.TvSeries,
                uniqueUrl=url,
                posterUrl=fixed_poster,
                backgroundPosterUrl=fixed_backdrop,
                year=fixed_year,
                plot=fixed_plot,
                episodes=episodes,
                actors=actors,
                score=score,
                tags=list(metadata.values())
            )
        else:
            hrefs = []
            for a in parser.css("div.download-item a"):
                h = a.attributes.get("href")
                if h:
                    if not h.startswith("http"):
                        h = f"{self.main_url.rstrip('/')}/{h.lstrip('/')}"
                    hrefs.append(h)
            
            if tmdb_id:
                # Add direct players
                hrefs.append(f"https://player.videasy.net/movie/{tmdb_id}")
                hrefs.append(f"https://player.autoembed.cc/embed/movie/{tmdb_id}")

            return MovieLoadResponse(
                name=fixed_title,
                url=url,
                apiName=self.name,
                type=TvType.Movie,
                uniqueUrl=url,
                dataUrl=json.dumps(list(set(hrefs))),
                posterUrl=fixed_poster,
                backgroundPosterUrl=fixed_backdrop,
                year=fixed_year,
                plot=fixed_plot,
                actors=actors,
                score=score,
                tags=list(metadata.values())
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
            
            if not resolved: continue
            
            if await load_extractor(resolved, self.main_url, callback, subtitle_callback):
                found = True
        return found
