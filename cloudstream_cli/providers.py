import asyncio
import json
import re
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any, Union
from .base import MainAPI
from .models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, HomePageResponse, HomePageList, MainPageRequest,
    ExtractorLink, SubtitleFile
)
from .network import Session

class TmdbProvider(MainAPI):
    name: str = "TMDB"
    main_url: str = "https://www.themoviedb.org"
    has_main_page: bool = True
    
    _api_key = "e6333b32409e02a4a6eba6fb7ff866bb"
    _base_url = "https://api.themoviedb.org/3"
    _image_url = "https://image.tmdb.org/t/p/w500"

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()

    def _get_image_url(self, path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        return f"{self._image_url}{path}" if path.startswith("/") else path

    def _get_url(self, id: int, is_tv: bool) -> str:
        return f"{self.main_url}/{'tv' if is_tv else 'movie'}/{id}"

    def _parse_year(self, date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        try:
            return int(date_str.split("-")[0])
        except (ValueError, IndexError):
            return None

    def _parse_timestamp(self, date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        url = f"{self._base_url}/search/multi"
        params = {
            "api_key": self._api_key,
            "query": query,
            "page": page,
            "language": "en-US",
            "include_adult": "false"
        }
        resp = await self._session.get(url, params=params)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        results = []
        for item in data.get("results", []):
            media_type = item.get("media_type")
            if media_type == "movie":
                results.append(MovieSearchResponse(
                    name=item.get("title") or item.get("original_title"),
                    url=self._get_url(item["id"], False),
                    apiName=self.name,
                    type=TvType.Movie,
                    posterUrl=self._get_image_url(item.get("poster_path")),
                    id=item["id"],
                    score=int(item.get("vote_average", 0) * 10) if item.get("vote_average") else None,
                    year=self._parse_year(item.get("release_date"))
                ))
            elif media_type == "tv":
                results.append(TvSeriesSearchResponse(
                    name=item.get("name") or item.get("original_name"),
                    url=self._get_url(item["id"], True),
                    apiName=self.name,
                    type=TvType.TvSeries,
                    posterUrl=self._get_image_url(item.get("poster_path")),
                    id=item["id"],
                    score=int(item.get("vote_average", 0) * 10) if item.get("vote_average") else None,
                    year=self._parse_year(item.get("first_air_date"))
                ))
        return results

    async def getMainPage(self, page: int = 1, request: Optional[MainPageRequest] = None) -> Optional[HomePageResponse]:
        movie_url = f"{self._base_url}/discover/movie"
        tv_url = f"{self._base_url}/discover/tv"
        params = {
            "api_key": self._api_key,
            "page": page,
            "language": "en-US"
        }
        
        movie_task = self._session.get(movie_url, params=params)
        tv_task = self._session.get(tv_url, params=params)
        
        movie_resp, tv_resp = await asyncio.gather(movie_task, tv_task)
        
        items = []
        if movie_resp.status_code == 200:
            movie_results = []
            for item in movie_resp.json().get("results", []):
                movie_results.append(MovieSearchResponse(
                    name=item.get("title") or item.get("original_title"),
                    url=self._get_url(item["id"], False),
                    apiName=self.name,
                    type=TvType.Movie,
                    posterUrl=self._get_image_url(item.get("poster_path")),
                    id=item["id"],
                    score=int(item.get("vote_average", 0) * 10) if item.get("vote_average") else None,
                    year=self._parse_year(item.get("release_date"))
                ))
            items.append(HomePageList("Popular Movies", movie_results))
            
        if tv_resp.status_code == 200:
            tv_results = []
            for item in tv_resp.json().get("results", []):
                tv_results.append(TvSeriesSearchResponse(
                    name=item.get("name") or item.get("original_name"),
                    url=self._get_url(item["id"], True),
                    apiName=self.name,
                    type=TvType.TvSeries,
                    posterUrl=self._get_image_url(item.get("poster_path")),
                    id=item["id"],
                    score=int(item.get("vote_average", 0) * 10) if item.get("vote_average") else None,
                    year=self._parse_year(item.get("first_air_date"))
                ))
            items.append(HomePageList("Popular Series", tv_results))
            
        return HomePageResponse(items, hasNext=True)

    async def load(self, url: str) -> Optional[LoadResponse]:
        match = re.search(r"themoviedb\.org/(movie|tv)/(\d+)", url)
        if not match:
            return None
        
        media_type = match.group(1)
        tmdb_id = int(match.group(2))
        is_tv = media_type == "tv"
        
        details_url = f"{self._base_url}/{media_type}/{tmdb_id}"
        params = {
            "api_key": self._api_key,
            "append_to_response": "external_ids,videos,credits",
            "language": "en-US"
        }
        
        resp = await self._session.get(details_url, params=params)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        imdb_id = data.get("external_ids", {}).get("imdb_id")
        
        def make_tmdb_link(episode=None, season=None):
            return json.dumps({
                "imdbID": imdb_id,
                "tmdbID": tmdb_id,
                "episode": episode,
                "season": season,
                "movieName": data.get("name") or data.get("title")
            })

        common_args = {
            "name": data.get("name") or data.get("title"),
            "url": url,
            "apiName": self.name,
            "type": TvType.TvSeries if is_tv else TvType.Movie,
            "uniqueUrl": make_tmdb_link(),
            "posterUrl": self._get_image_url(data.get("poster_path")),
            "plot": data.get("overview"),
            "score": int(data.get("vote_average", 0) * 10) if data.get("vote_average") else None,
            "tags": [g["name"] for g in data.get("genres", [])],
            "year": self._parse_year(data.get("first_air_date") if is_tv else data.get("release_date")),
            "actors": [
                ActorData(Actor(c["name"], self._get_image_url(c.get("profile_path"))), roleString=c.get("character"))
                for c in data.get("credits", {}).get("cast", [])
            ],
            "trailers": [
                TrailerData(f"https://www.youtube.com/watch?v={v['key']}", None, False)
                for v in data.get("videos", {}).get("results", [])
                if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]
            ]
        }

        if is_tv:
            episodes = []
            seasons = data.get("seasons", [])
            season_tasks = []
            for season in seasons:
                season_number = season.get("season_number")
                if season_number == 0: continue 
                
                season_url = f"{self._base_url}/tv/{tmdb_id}/season/{season_number}"
                s_params = {
                    "api_key": self._api_key,
                    "language": "en-US"
                }
                season_tasks.append(self._session.get(season_url, params=s_params))
            
            season_responses = await asyncio.gather(*season_tasks)
            for s_resp in season_responses:
                if s_resp.status_code == 200:
                    s_data = s_resp.json()
                    season_number = s_data.get("season_number")
                    for ep in s_data.get("episodes", []):
                        ep_num = ep.get("episode_number")
                        episodes.append(Episode(
                            data=make_tmdb_link(ep_num, season_number),
                            name=ep.get("name"),
                            season=season_number,
                            episode=ep_num,
                            posterUrl=self._get_image_url(ep.get("still_path")),
                            score=int(ep.get("vote_average", 0) * 10) if ep.get("vote_average") else None,
                            description=ep.get("overview"),
                            date=self._parse_timestamp(ep.get("air_date"))
                        ))
            
            return TvSeriesLoadResponse(**common_args, episodes=episodes)
        else:
            return MovieLoadResponse(**common_args, dataUrl=make_tmdb_link())

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        return False

def get_providers(session: Optional[Session] = None) -> List[MainAPI]:
    return [TmdbProvider(session)]
