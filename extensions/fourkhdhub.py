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
from cloudstream_cli.orchestrator import load_extractor

class FourKHDHubProvider(MainAPI):
    name: str = "4K HDHUB"
    main_url: str = "https://4khdhub.dad"
    lang: str = "en"
    supported_types = {TvType.Movie, TvType.TvSeries, TvType.Anime}
    
    TMDB_API = "https://wild-surf-4a0d.phisher1.workers.dev"
    TMDB_API_KEY = "1865f43a0549ca50d341dd9ab8b29f49"
    TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/original"

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

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
                href = f"{self.main_url}{href}" if href.startswith("/") else f"{self.main_url}/{href}"
                
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
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
        
        parser = self._session.parse_html(resp.text)
        title_raw = parser.css_first("h1.page-title")
        if not title_raw: return None
        title = title_raw.text().split("(")[0].strip()
        
        poster_el = parser.css_first("meta[property='og:image']")
        poster = poster_el.attributes.get("content") if poster_el else None
        
        tags = [t.text().strip() for t in parser.css("div.mt-2 span.badge")]
        is_movie = "Movies" in tags
        tv_type = TvType.Movie if is_movie else TvType.TvSeries
        
        year_el = parser.css_first("div.mt-2 span")
        year = None
        if year_el:
            try:
                year = int(re.search(r"(\d{4})", year_el.text()).group(1))
            except:
                pass

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

        if tv_type == TvType.TvSeries:
            episodes = []
            # Parse episodes from page
            # <div class="episodes-list"> <div class="season-item">
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
                                h = f"{self.main_url}{h}" if h.startswith("/") else f"{self.main_url}/{h}"
                            hrefs.append(h)
                    
                    if hrefs:
                        episodes.append(Episode(
                            name=f"Episode {ep_num}",
                            season=season_num,
                            episode=ep_num,
                            data=json.dumps(hrefs)
                        ))
            
            # Additional download items for full seasons
            for item in parser.css("div.download-item"):
                header = item.css_first("div.flex-1.text-left.font-semibold")
                if not header: continue
                header_text = header.text()
                
                season_match = re.search(r"S(\d+)", header_text)
                if not season_match: continue
                season_num = int(season_match.group(1))
                
                hrefs = []
                for a in item.css("a"):
                    h = a.attributes.get("href")
                    if h:
                        if not h.startswith("http"):
                            h = f"{self.main_url}{h}" if h.startswith("/") else f"{self.main_url}/{h}"
                        hrefs.append(h)
                
                if hrefs:
                    # If we already have episodes for this season, this might be redundant or a full pack
                    # Kotlin logic adds them as separate episodes with high numbers or something?
                    # "nextEpisode = maxEpisodePerSeason.getOrDefault(season, 0) + 1"
                    # For simplicity, let's just add them if not already present or as a special entry
                    episodes.append(Episode(
                        name=f"Season {season_num} Full Pack",
                        season=season_num,
                        episode=0, # Use 0 for full pack
                        data=json.dumps(hrefs)
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
                tags=tags
            )
        else:
            hrefs = []
            for a in parser.css("div.download-item a"):
                h = a.attributes.get("href")
                if h:
                    if not h.startswith("http"):
                        h = f"{self.main_url}{h}" if h.startswith("/") else f"{self.main_url}/{h}"
                    hrefs.append(h)
            
            return MovieLoadResponse(
                name=fixed_title,
                url=url,
                apiName=self.name,
                type=TvType.Movie,
                uniqueUrl=url,
                dataUrl=json.dumps(hrefs),
                posterUrl=fixed_poster,
                backgroundPosterUrl=fixed_backdrop,
                year=fixed_year,
                plot=fixed_plot,
                actors=actors,
                score=score,
                tags=tags
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
                resolved = await self._get_redirect_links(link)
            
            if not resolved: continue
            
            # HubCloud handling as in Kotlin
            if "hubcloud" in resolved.lower():
                # We can try load_extractor first, it might have HubCloud
                if await load_extractor(resolved, self.main_url, callback, subtitle_callback):
                    found = True
            else:
                if await load_extractor(resolved, self.main_url, callback, subtitle_callback):
                    found = True
        return found

    async def _get_redirect_links(self, url: str) -> str:
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return ""
        
        html = resp.text
        # s\('o','([A-Za-z0-9+/=]+)'|ck\('_wp_http_\d+','([^']+)'
        regex = r"s\('o','([A-Za-z0-9+/=]+)'|ck\('_wp_http_\d+','([^']+)'"
        matches = re.findall(regex, html)
        combined = ""
        for m in matches:
            combined += m[0] or m[1]
            
        if not combined: return ""
        
        try:
            def rot13(s):
                res = ""
                for c in s:
                    if 'A' <= c <= 'Z': res += chr((ord(c) - ord('A') + 13) % 26 + ord('A'))
                    elif 'a' <= c <= 'z': res += chr((ord(c) - ord('a') + 13) % 26 + ord('a'))
                    else: res += c
                return res

            def b64_decode(s):
                return base64.b64decode(s + "=" * (-len(s) % 4)).decode('utf-8', errors='ignore')

            # base64Decode(pen(base64Decode(base64Decode(combined))))
            # pen is rot13
            step1 = b64_decode(combined)
            step2 = b64_decode(step1)
            step3 = rot13(step2)
            decoded = b64_decode(step3)
            
            json_data = json.loads(decoded)
            
            # json.optString("o")
            o = json_data.get("o")
            if o:
                return b64_decode(o).strip()
            
            data = json_data.get("data")
            wp = json_data.get("blog_url")
            if data and wp:
                # data is base64 encoded
                data_decoded = base64.b64decode(data).decode('utf-8', errors='ignore')
                # app.get("$wp?re=$data")
                resp2 = await self._session.get(f"{wp}?re={data_decoded}", headers=self.headers)
                if resp2.status_code == 200:
                    return resp2.text.strip()
        except Exception as e:
            print(f"Error in redirect: {e}")
            
        return ""
