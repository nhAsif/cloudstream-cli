import hmac
import hashlib
import base64
import time
import json
import random
import re
from typing import List, Optional, Callable, Dict, Any, Set
from urllib.parse import urlparse, parse_qs, quote

from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse, TvSeriesSearchResponse,
    LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, HomePageResponse, HomePageList, MainPageRequest,
    ExtractorLink, SubtitleFile, ExtractorLinkType
)
from cloudstream_cli.network import Session

class MovieBoxProvider(MainAPI):
    name: str = "MovieBox"
    main_url: str = "https://api3.aoneroom.com"
    lang: str = "hi"
    has_main_page: bool = True
    supported_types: Set[TvType] = {TvType.Movie, TvType.TvSeries}

    _secret_key_default_raw = "NzZpUmwwN3MweFNOOWpxbUVXQXQ3OUVCSlp1bElRSXNWNjRGWnIyTw=="
    _secret_key_alt_raw = "WHFuMm5uTzQxL0w5Mm8xaXVYaFNMSFRiWHZZNFo1Wlo2Mm04bVNMQQ=="

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.device_id = self._generate_device_id()
        # Double decode secret keys
        self._secret_key_default = base64.b64decode(base64.b64decode(self._secret_key_default_raw).decode('iso-8859-1'))
        self._secret_key_alt = base64.b64decode(base64.b64decode(self._secret_key_alt_raw).decode('iso-8859-1'))
        self.brand_models = {
            "Samsung": ["SM-S918B", "SM-A528B", "SM-M336B"],
            "Xiaomi": ["2201117TI", "M2012K11AI", "Redmi Note 11"],
            "OnePlus": ["LE2111", "CPH2449", "IN2023"],
            "Google": ["Pixel 6", "Pixel 7", "Pixel 8"],
            "Realme": ["RMX3085", "RMX3360", "RMX3551"]
        }

    def _generate_device_id(self) -> str:
        # Kotlin version uses 16 random bytes joined as hex -> 32 chars
        return "".join([random.choice("0123456789abcdef") for _ in range(32)])

    def _random_brand_model(self) -> Dict[str, str]:
        brand = random.choice(list(self.brand_models.keys()))
        model = random.choice(self.brand_models[brand])
        return {"brand": brand, "model": model}

    def _md5(self, data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    def _generate_x_client_token(self, timestamp: Optional[int] = None) -> str:
        ts = str(timestamp or int(time.time() * 1000))
        reversed_ts = ts[::-1]
        hash_val = self._md5(reversed_ts.encode())
        return f"{ts},{hash_val}"

    def _build_canonical_string(
        self,
        method: str,
        accept: Optional[str],
        content_type: Optional[str],
        url: str,
        body: Optional[str],
        timestamp: int
    ) -> str:
        parsed = urlparse(url)
        path = parsed.path
        
        # Build query string with sorted parameters
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_keys = sorted(query_params.keys())
        query_parts = []
        for key in sorted_keys:
            # Kotlin code: parsed.getQueryParameters(key).joinToString("&") { value -> "$key=$value" }
            # It seems it doesn't URL encode the values in the canonical string
            for val in sorted(query_params[key]):
                query_parts.append(f"{key}={val}")
        
        canonical_url = f"{path}?{'&'.join(query_parts)}" if query_parts else path

        body_bytes = body.encode('utf-8') if body else None
        body_hash = ""
        body_length = ""
        if body_bytes:
            trimmed = body_bytes[:102400]
            body_hash = self._md5(trimmed)
            body_length = str(len(body_bytes))

        return (
            f"{method.upper()}\n"
            f"{accept or ''}\n"
            f"{content_type or ''}\n"
            f"{body_length}\n"
            f"{timestamp}\n"
            f"{body_hash}\n"
            f"{canonical_url}"
        )

    def _generate_x_tr_signature(
        self,
        method: str,
        accept: Optional[str],
        content_type: Optional[str],
        url: str,
        body: Optional[str] = None,
        use_alt_key: bool = False,
        timestamp: Optional[int] = None
    ) -> str:
        ts = timestamp or int(time.time() * 1000)
        canonical = self._build_canonical_string(method, accept, content_type, url, body, ts)
        secret = self._secret_key_alt if use_alt_key else self._secret_key_default
        
        signature = hmac.new(secret, canonical.encode('utf-8'), hashlib.md5).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        return f"{ts}|2|{signature_b64}"

    def _get_client_info(self, bm: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if not bm:
            bm = self._random_brand_model()
        return {
            "package_name": "com.community.mbox.in",
            "version_name": "3.0.03.0529.03",
            "version_code": 50020042,
            "os": "android",
            "os_version": "16",
            "device_id": self.device_id,
            "install_store": "ps",
            "gaid": "d7578036d13336cc",
            "brand": bm["brand"].lower(),
            "model": bm["model"],
            "system_language": "en",
            "net": "NETWORK_WIFI",
            "region": "IN",
            "timezone": "Asia/Calcutta",
            "sp_code": ""
        }

    async def getMainPage(self, page: int = 1, request: Optional[MainPageRequest] = None) -> Optional[HomePageResponse]:
        if not request:
            # Default to Trending if no request
            request = MainPageRequest("Trending", "4516404531735022304")
            
        per_page = 15
        is_list = "|" in request.data
        if is_list:
            url = f"{self.main_url}/wefeed-mobile-bff/subject-api/list"
        else:
            url = f"{self.main_url}/wefeed-mobile-bff/tab/ranking-list?tabId=0&categoryType={request.data}&page={page}&perPage={per_page}"

        json_body = None
        if is_list:
            main_parts = request.data.split(";")[0].split("|")
            channel_id = main_parts[1] if len(main_parts) > 1 else ""
            
            options = {}
            if ";" in request.data:
                opt_str = request.data.split(";", 1)[1]
                for part in opt_str.split(";"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        options[k] = v
            
            body_dict = {
                "page": page,
                "perPage": per_page,
                "channelId": channel_id,
                "classify": options.get("classify", "All"),
                "country": options.get("country", "All"),
                "year": options.get("year", "All"),
                "genre": options.get("genre", "All"),
                "sort": options.get("sort", "ForYou")
            }
            json_body = json.dumps(body_dict, separators=(',', ':'))

        x_client_token = self._generate_x_client_token()
        method = "POST" if is_list else "GET"
        content_type = "application/json; charset=utf-8" if is_list else "application/json"
        x_tr_signature = self._generate_x_tr_signature(method, "application/json", content_type, url, json_body)

        bm = self._random_brand_model()
        headers = {
            "user-agent": f"com.community.mbox.in/50020042 (Linux; U; Android 16; en_IN; {bm['model']}; Build/BP22.250325.006; Cronet/133.0.6876.3)",
            "accept": "application/json",
            "content-type": content_type,
            "connection": "keep-alive",
            "x-client-token": x_client_token,
            "x-tr-signature": x_tr_signature,
            "x-client-info": json.dumps(self._get_client_info(bm), separators=(',', ':')),
            "x-client-status": "0",
            "x-play-mode": "2"
        }

        if is_list:
            resp = await self._session.post(url, headers=headers, data=json_body)
        else:
            resp = await self._session.get(url, headers=headers)

        if resp.status_code != 200:
            return None

        try:
            root = resp.json()
            data_node = root.get("data", {})
            items = data_node.get("items") or data_node.get("subjects") or []
            
            results = []
            for item in items:
                title = item.get("title", "").split("[")[0].strip()
                subject_id = item.get("subjectId")
                if not subject_id: continue
                
                cover_url = item.get("cover", {}).get("url")
                subject_type = item.get("subjectType", 1)
                tv_type = TvType.TvSeries if subject_type in [2, 7] else TvType.Movie
                
                results.append(MovieSearchResponse(
                    name=title,
                    url=subject_id,
                    apiName=self.name,
                    type=tv_type,
                    posterUrl=cover_url,
                    score=int(float(item.get("imdbRatingValue", 0)) * 10) if item.get("imdbRatingValue") else None
                ))
            
            return HomePageResponse([HomePageList(request.name, results)], hasNext=True)
        except Exception:
            return None

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        url = f"{self.main_url}/wefeed-mobile-bff/subject-api/search/v2"
        body_dict = {"page": page, "perPage": 20, "keyword": query}
        json_body = json.dumps(body_dict, separators=(',', ':'))
        
        x_client_token = self._generate_x_client_token()
        x_tr_signature = self._generate_x_tr_signature("POST", "application/json", "application/json; charset=utf-8", url, json_body)
        
        bm = self._random_brand_model()
        headers = {
            "user-agent": f"com.community.mbox.in/50020042 (Linux; U; Android 16; en_IN; {bm['model']}; Build/BP22.250325.006; Cronet/133.0.6876.3)",
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "connection": "keep-alive",
            "x-client-token": x_client_token,
            "x-tr-signature": x_tr_signature,
            "x-client-info": json.dumps(self._get_client_info(bm), separators=(',', ':')),
            "x-client-status": "0"
        }
        
        resp = await self._session.post(url, headers=headers, data=json_body)
        if resp.status_code != 200:
            return None
            
        try:
            root = resp.json()
            results_node = root.get("data", {}).get("results", [])
            search_list = []
            for result in results_node:
                subjects = result.get("subjects", [])
                for subject in subjects:
                    title = subject.get("title")
                    subject_id = subject.get("subjectId")
                    if not title or not subject_id: continue
                    
                    cover_url = subject.get("cover", {}).get("url")
                    subject_type = subject.get("subjectType", 1)
                    tv_type = TvType.TvSeries if subject_type in [2, 7] else TvType.Movie
                    
                    search_list.append(MovieSearchResponse(
                        name=title,
                        url=subject_id,
                        apiName=self.name,
                        type=tv_type,
                        posterUrl=cover_url,
                        score=int(float(subject.get("imdbRatingValue", 0)) * 10) if subject.get("imdbRatingValue") else None
                    ))
            return search_list
        except Exception:
            return None

    async def load(self, url: str) -> Optional[LoadResponse]:
        # Handle both full URLs and just subject IDs
        subject_id = url
        if "subjectId=" in url:
            match = re.search(r"subjectId=([^&]+)", url)
            if match:
                subject_id = match.group(1)
        elif "/" in url:
            subject_id = url.split("/")[-1]

        final_url = f"{self.main_url}/wefeed-mobile-bff/subject-api/get?subjectId={subject_id}"
        x_client_token = self._generate_x_client_token()
        x_tr_signature = self._generate_x_tr_signature("GET", "application/json", "application/json", final_url)
        
        bm = self._random_brand_model()
        headers = {
            "user-agent": f"com.community.mbox.in/50020042 (Linux; U; Android 16; en_IN; {bm['model']}; Build/BP22.250325.006; Cronet/133.0.6876.3)",
            "accept": "application/json",
            "content-type": "application/json",
            "connection": "keep-alive",
            "x-client-token": x_client_token,
            "x-tr-signature": x_tr_signature,
            "x-client-info": json.dumps(self._get_client_info(bm), separators=(',', ':')),
            "x-client-status": "0",
            "x-play-mode": "2"
        }
        
        resp = await self._session.get(final_url, headers=headers)
        if resp.status_code != 200:
            return None
            
        try:
            root = resp.json()
            data = root.get("data")
            if not data: return None
            
            title = data.get("title", "").split("[")[0].strip()
            description = data.get("description")
            release_date = data.get("releaseDate")
            duration_str = data.get("duration")
            imdb_rating = data.get("imdbRatingValue")
            year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
            
            cover_url = data.get("cover", {}).get("url")
            subject_type = data.get("subjectType", 1)
            tv_type = TvType.TvSeries if subject_type in [2, 7] else TvType.Movie
            
            actors = []
            for staff in data.get("staffList", []):
                if staff.get("staffType") == 1: # Actor
                    actors.append(ActorData(
                        Actor(staff.get("name"), staff.get("avatarUrl")),
                        roleString=staff.get("character")
                    ))

            tags = [t.strip() for t in data.get("genre", "").split(",") if t.strip()]
            
            duration_minutes = None
            if duration_str:
                match = re.search(r"(\d+)h\s*(\d+)m", duration_str)
                if match:
                    h = int(match.group(1))
                    m = int(match.group(2))
                    duration_minutes = h * 60 + m
                else:
                    duration_minutes = int(duration_str.replace("m", "")) if duration_str.endswith("m") else None

            common_args = {
                "name": title,
                "url": url,
                "apiName": self.name,
                "type": tv_type,
                "uniqueUrl": subject_id,
                "posterUrl": cover_url,
                "plot": description,
                "year": year,
                "score": int(float(imdb_rating) * 10) if imdb_rating else None,
                "tags": tags,
                "duration": duration_minutes,
                "actors": actors,
                "backgroundPosterUrl": cover_url
            }

            if tv_type == TvType.TvSeries:
                all_subject_ids = [subject_id]
                for dub in data.get("dubs", []):
                    sid = dub.get("subjectId")
                    if sid and sid not in all_subject_ids:
                        all_subject_ids.append(sid)
                
                episode_map = {} # (season, episode) -> info
                
                for sid in all_subject_ids:
                    season_url = f"{self.main_url}/wefeed-mobile-bff/subject-api/season-info?subjectId={sid}"
                    season_sig = self._generate_x_tr_signature("GET", "application/json", "application/json", season_url)
                    s_headers = headers.copy()
                    s_headers["x-tr-signature"] = season_sig
                    
                    s_resp = await self._session.get(season_url, headers=s_headers)
                    if s_resp.status_code == 200:
                        s_root = s_resp.json()
                        seasons = s_root.get("data", {}).get("seasons", [])
                        for season in seasons:
                            s_num = season.get("se", 1)
                            max_ep = season.get("maxEp", 1)
                            for e_num in range(1, max_ep + 1):
                                if (s_num, e_num) not in episode_map:
                                    episode_map[(s_num, e_num)] = f"{sid}|{s_num}|{e_num}"
                
                episodes = []
                for (s_num, e_num) in sorted(episode_map.keys()):
                    episodes.append(Episode(
                        data=episode_map[(s_num, e_num)],
                        name=f"Episode {e_num}",
                        season=s_num,
                        episode=e_num,
                        posterUrl=cover_url
                    ))
                
                if not episodes:
                    episodes.append(Episode(
                        data=f"{subject_id}|1|1",
                        name="Episode 1",
                        season=1,
                        episode=1,
                        posterUrl=cover_url
                    ))
                
                return TvSeriesLoadResponse(**common_args, episodes=episodes)
            
            return MovieLoadResponse(**common_args, dataUrl=subject_id)
        except Exception:
            return None

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        try:
            parts = data.split("|")
            original_subject_id = parts[0]
            if "subjectId=" in original_subject_id:
                match = re.search(r"subjectId=([^&]+)", original_subject_id)
                if match:
                    original_subject_id = match.group(1)
            
            season = int(parts[1]) if len(parts) > 1 else 0
            episode = int(parts[2]) if len(parts) > 2 else 0
            
            # 1. Get Dubs
            subject_url = f"{self.main_url}/wefeed-mobile-bff/subject-api/get?subjectId={original_subject_id}"
            x_client_token = self._generate_x_client_token()
            x_tr_signature = self._generate_x_tr_signature("GET", "application/json", "application/json", subject_url)
            
            bm = self._random_brand_model()
            # Note: Using OneRoom specific headers as seen in Kotlin
            headers = {
                "user-agent": f"com.community.oneroom/50020088 (Linux; U; Android 13; en_US; {bm['model']}; Build/TQ3A.230901.001; Cronet/145.0.7582.0)",
                "accept": "application/json",
                "content-type": "application/json",
                "connection": "keep-alive",
                "x-client-token": x_client_token,
                "x-tr-signature": x_tr_signature,
                "x-client-info": json.dumps({
                    "package_name": "com.community.oneroom",
                    "version_name": "3.0.13.0325.03",
                    "version_code": 50020088,
                    "os": "android",
                    "os_version": "13",
                    "install_ch": "ps",
                    "device_id": self.device_id,
                    "install_store": "ps",
                    "gaid": "1b2212c1-dadf-43c3-a0c8-bd6ce48ae22d",
                    "brand": bm["brand"],
                    "model": bm["model"],
                    "system_language": "en",
                    "net": "NETWORK_WIFI",
                    "region": "US",
                    "timezone": "Asia/Calcutta",
                    "sp_code": "",
                    "X-Play-Mode": "1",
                    "X-Idle-Data": "1",
                    "X-Family-Mode": "0",
                    "X-Content-Mode": "0"
                }, separators=(',', ':')),
                "x-client-status": "0"
            }
            
            resp = await self._session.get(subject_url, headers=headers)
            subject_ids = [] # (id, lang)
            token = None
            if resp.status_code == 200:
                root = resp.json()
                data_node = root.get("data", {})
                original_lang = "Original"
                dubs = data_node.get("dubs", [])
                for dub in dubs:
                    sid = dub.get("subjectId")
                    lan = dub.get("lanName")
                    if sid == original_subject_id:
                        original_lang = lan
                    else:
                        subject_ids.append((sid, lan))
                subject_ids.insert(0, (original_subject_id, original_lang))
                
                x_user = resp.headers.get("x-user")
                if x_user:
                    try:
                        token = json.loads(x_user).get("token")
                    except:
                        pass

            # 2. Get Links for each Dub
            for sid, lang in subject_ids:
                play_url = f"{self.main_url}/wefeed-mobile-bff/subject-api/play-info?subjectId={sid}&se={season}&ep={episode}"
                x_client_token = self._generate_x_client_token()
                x_tr_signature = self._generate_x_tr_signature("GET", "application/json", "application/json", play_url)
                
                p_headers = headers.copy()
                p_headers["x-tr-signature"] = x_tr_signature
                p_headers["x-client-token"] = x_client_token
                if token:
                    p_headers["Authorization"] = f"Bearer {token}"
                
                p_resp = await self._session.get(play_url, headers=p_headers)
                if p_resp.status_code == 200:
                    p_root = p_resp.json()
                    streams = p_root.get("data", {}).get("streams", [])
                    for stream in streams:
                        stream_url = stream.get("url")
                        if not stream_url: continue
                        
                        stream_id = stream.get("id")
                        resolutions = stream.get("resolutions", "")
                        format_val = stream.get("format", "")
                        sign_cookie = stream.get("signCookie")
                        
                        quality = self._get_highest_quality(resolutions)
                        
                        link_type = ExtractorLinkType.VIDEO
                        if ".m3u8" in stream_url.lower() or format_val.upper() == "HLS":
                            link_type = ExtractorLinkType.M3U8
                        elif ".mpd" in stream_url.lower():
                            link_type = ExtractorLinkType.DASH
                        
                        l_headers = {"Referer": self.main_url}
                        if sign_cookie:
                            l_headers["Cookie"] = sign_cookie
                            
                        callback(ExtractorLink(
                            source=f"{self.name} {lang.replace('dub', 'Audio')}",
                            name=f"{self.name} ({lang.replace('dub', 'Audio')})",
                            url=stream_url,
                            referer=self.main_url,
                            quality=quality or 0,
                            type=link_type,
                            headers=l_headers
                        ))
                        
                        # Subtitles
                        if stream_id:
                            await self._resolve_subtitles(sid, stream_id, token, lang, subtitle_callback)

                    # Fallback resource detectors
                    if not streams:
                        detectors = p_root.get("data", {}).get("resourceDetectors", [])
                        for detector in detectors:
                            for video in detector.get("resolutionList", []):
                                link = video.get("resourceLink")
                                if not link: continue
                                q = video.get("resolution", 0)
                                se = video.get("se")
                                ep = video.get("ep")
                                
                                callback(ExtractorLink(
                                    source=f"{self.name} {lang.replace('dub', 'Audio')}",
                                    name=f"{self.name} S{se}E{ep} {q}p ({lang.replace('dub', 'Audio')})",
                                    url=link,
                                    referer=self.main_url,
                                    quality=q,
                                    type=ExtractorLinkType.VIDEO,
                                    headers={"Referer": self.main_url}
                                ))
            return True
        except Exception:
            return False

    async def _resolve_subtitles(self, subject_id: str, stream_id: str, token: str, dub_lang: str, callback: Callable[[SubtitleFile], None]):
        # /get-stream-captions
        sub_url = f"{self.main_url}/wefeed-mobile-bff/subject-api/get-stream-captions?subjectId={subject_id}&streamId={stream_id}"
        x_client_token = self._generate_x_client_token()
        # Kotlin uses empty strings for accept and content-type in signature for this call
        x_tr_signature = self._generate_x_tr_signature("GET", "", "", sub_url)
        
        headers = {
            "Authorization": f"Bearer {token}" if token else "",
            "x-client-token": x_client_token,
            "x-tr-signature": x_tr_signature,
            "accept": "application/json",
            "x-client-status": "0"
        }
        
        resp = await self._session.get(sub_url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            for caption in data.get("extCaptions", []):
                url = caption.get("url")
                if url:
                    lang = caption.get("language") or caption.get("lanName") or caption.get("lan") or "Unknown"
                    callback(SubtitleFile(url, f"{lang} ({dub_lang.replace('dub', 'Audio')})"))

        # /get-ext-captions
        sub_url_ext = f"{self.main_url}/wefeed-mobile-bff/subject-api/get-ext-captions?subjectId={subject_id}&resourceId={stream_id}&episode=0"
        x_client_token_ext = self._generate_x_client_token()
        x_tr_signature_ext = self._generate_x_tr_signature("GET", "", "", sub_url_ext)
        
        headers_ext = headers.copy()
        headers_ext["x-tr-signature"] = x_tr_signature_ext
        headers_ext["x-client-token"] = x_client_token_ext
        
        resp_ext = await self._session.get(sub_url_ext, headers=headers_ext)
        if resp_ext.status_code == 200:
            data_ext = resp_ext.json().get("data", {})
            for caption in data_ext.get("extCaptions", []):
                url = caption.get("url")
                if url:
                    lang = caption.get("lan") or caption.get("lanName") or caption.get("language") or "Unknown"
                    callback(SubtitleFile(url, f"{lang} ({dub_lang.replace('dub', 'Audio')})"))

    def _get_highest_quality(self, resolutions: str) -> Optional[int]:
        qualities = [
            ("2160", 2160),
            ("1440", 1440),
            ("1080", 1080),
            ("720", 720),
            ("480", 480),
            ("360", 360),
            ("240", 240)
        ]
        for label, val in qualities:
            if label in resolutions:
                return val
        return None

def get_provider(session: Optional[Session] = None) -> MainAPI:
    return MovieBoxProvider(session)
