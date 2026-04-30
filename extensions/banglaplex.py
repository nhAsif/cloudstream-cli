import re
import urllib.parse
from typing import List, Optional, Callable, Dict, Any
from cloudstream_cli.base import MainAPI, ExtractorApi
from cloudstream_cli.models import (
    TvType, SearchResponse, MovieSearchResponse,
    LoadResponse, MovieLoadResponse,
    ExtractorLink, SubtitleFile, SearchQuality,
    ExtractorLinkType
)
from cloudstream_cli.network import Session
from cloudstream_cli.orchestrator import load_extractor, get_manager
from cloudstream_cli.utils import fix_url

class Xcloud(ExtractorApi):
    name: str = "XCloud"
    main_url: str = "https://xcloud.forum"
    
    def __init__(self, session: Session, name: str = "XCloud", main_url: str = "https://xcloud.forum"):
        self._session = session
        self.name = name
        self.main_url = main_url

    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        resp = await self._session.get(url)
        if resp.status_code != 200:
            return
            
        parser = self._session.parse_html(resp.text)
        
        direct_btn = None
        for a in parser.css("div.vd a.btn-primary"):
            if "generate direct" in a.text().lower():
                direct_btn = a
                break
        
        if not direct_btn:
            return
            
        href = direct_btn.attributes.get("href")
        if not href:
            return
            
        href = fix_url(href, self.main_url)
            
        resp2 = await self._session.get(href)
        if resp2.status_code != 200:
            return
            
        parser2 = self._session.parse_html(resp2.text)
        
        iframe_el = parser2.css_first("iframe")
        iframe_src = iframe_el.attributes.get("src") if iframe_el else None
        
        for a in parser2.css("h2 a.btn"):
            link_href = a.attributes.get("href")
            if link_href:
                link_href = fix_url(link_href, self.main_url)
                callback(ExtractorLink(
                    source=self.name,
                    name=self.name,
                    url=link_href,
                    referer=href,
                    quality=0,
                    type=ExtractorLinkType.VIDEO
                ))
        
        if iframe_src:
            iframe_src = fix_url(iframe_src, self.main_url)
            callback(ExtractorLink(
                source=self.name,
                name=self.name,
                url=iframe_src,
                referer=href,
                quality=0,
                type=ExtractorLinkType.VIDEO
            ))

class Plextream(ExtractorApi):
    name: str = "Plextream"
    main_url: str = "https://plextream.work"
    
    def __init__(self, session: Session):
        self._session = session

    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        resp = await self._session.get(url, headers={"Referer": referer} if referer else {})
        if resp.status_code != 200:
            return
            
        parser = self._session.parse_html(resp.text)
        
        for btn in parser.css(".menu-card button"):
            onclick = btn.attributes.get("onclick", "")
            if "changeServer('" in onclick:
                video_url = onclick.split("changeServer('")[1].split("'")[0]
                if video_url:
                    # In Kotlin: videoUrl.contains("rpmvid") || videoUrl.contains("rpmshare") || videoUrl.contains("strp2p")
                    # It calls VidStack().getUrl or loadExtractor.
                    # For simplicity, we use load_extractor which should handle those if registered.
                    await load_extractor(video_url, url, callback, subtitle_callback)

class BanglaPlexProvider(MainAPI):
    name: str = "Banglaplex"
    main_url: str = "https://banglaplex.click"
    lang: str = "bn"
    supported_types = {TvType.Movie, TvType.TvSeries}

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        # Register local extractors
        manager = get_manager()
        manager.register_extractor(Xcloud(self._session, name="XCloud", main_url="https://xcloud.forum"))
        manager.register_extractor(Xcloud(self._session, name="XCloud", main_url="https://xcloud.click"))
        manager.register_extractor(Plextream(self._session))

    def _get_quality(self, quality_str: str) -> SearchQuality:
        quality_str = quality_str.lower()
        if "4k" in quality_str: return SearchQuality.FourK
        if "720" in quality_str: return SearchQuality.SD
        if "1080" in quality_str: return SearchQuality.HD
        return SearchQuality.HD

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        if page == 1:
            url = f"{self.main_url}/search?q={urllib.parse.quote(query)}"
        else:
            new_page_number = page * 12
            url = f"{self.main_url}/search?q={urllib.parse.quote(query)}&per_page={new_page_number}"
            
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
            
        parser = self._session.parse_html(resp.text)
        results = []
        
        for item in parser.css("div.movie-container > div.col-md-2"):
            title_el = item.css_first("div.movie-img > div.movie-title > h3 > a")
            if not title_el: continue
            
            title = title_el.text().strip()
            href = title_el.attributes.get("href")
            href = fix_url(href, self.main_url)
                
            poster_container = item.css_first("div.latest-movie-img-container")
            poster_url = None
            if poster_container:
                style = poster_container.attributes.get("style", "")
                match = re.search(r"url\('(.+?)'\)", style)
                if match:
                    poster_url = match.group(1)
                    poster_url = fix_url(poster_url, self.main_url)
            
            quality_el = item.css_first("span.label.label-primary")
            quality = self._get_quality(quality_el.text()) if quality_el else SearchQuality.HD
            
            score_el = item.css_first("span.label.label-imdb")
            score = None
            if score_el:
                score_text = score_el.text()
                if "IMDB" in score_text:
                    try:
                        score = int(float(score_text.split("IMDB")[-1].strip()) * 10)
                    except:
                        pass
            
            results.append(MovieSearchResponse(
                name=title,
                url=href,
                apiName=self.name,
                type=TvType.Movie,
                posterUrl=poster_url,
                quality=quality,
                score=score
            ))
            
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        resp = await self._session.get(url, headers=self.headers)
        if resp.status_code != 200:
            return None
            
        parser = self._session.parse_html(resp.text)
        
        title_el = parser.css_first("meta[property='og:title']")
        title = title_el.attributes.get("content", "").split("|")[0].strip() if title_el else "Unknown"
        
        poster_el = parser.css_first("#info > div > div > img")
        poster = poster_el.attributes.get("src") if poster_el else None
        poster = fix_url(poster, self.main_url)
            
        desc_el = parser.css_first("meta[property='og:description']")
        description = desc_el.attributes.get("content", "").strip() if desc_el else None
        
        return MovieLoadResponse(
            name=title,
            url=url,
            apiName=self.name,
            type=TvType.Movie,
            uniqueUrl=url,
            dataUrl=url,
            posterUrl=poster,
            plot=description
        )

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        resp = await self._session.get(data, headers=self.headers)
        if resp.status_code != 200:
            return False
            
        parser = self._session.parse_html(resp.text)
        
        # Parse iframes
        for iframe in parser.css("div.video-embed-container iframe"):
            src = iframe.attributes.get("src")
            if src:
                await load_extractor(src, data, callback, subtitle_callback)
        
        # Parse download buttons
        download_btn = parser.css_first("#download a")
        if download_btn:
            download_url = download_btn.attributes.get("href")
            if download_url:
                download_url = fix_url(download_url, self.main_url)
                
                resp2 = await self._session.get(download_url, headers=self.headers)
                if resp2.status_code == 200:
                    parser2 = self._session.parse_html(resp2.text)
                    
                    csrf_input = parser2.css_first("form input")
                    if csrf_input:
                        csrf_name = csrf_input.attributes.get("name")
                        csrf_value = csrf_input.attributes.get("value") or csrf_name
                        
                        post_data = {csrf_name: csrf_value}
                        resp3 = await self._session.post(download_url, data=post_data, headers=self.headers)
                        if resp3.status_code == 200:
                            parser3 = self._session.parse_html(resp3.text)
                            
                            for a in parser3.css("div.row > div.col-sm-8 > a"):
                                href = a.attributes.get("href")
                                if href:
                                    href = fix_url(href, self.main_url)
                                    await load_extractor(href, download_url, callback, subtitle_callback)
                            
        return True
