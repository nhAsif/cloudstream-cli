from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile
from ..network import Session
from ..utils import fix_url

class Xcloud(ExtractorApi):
    name: str = "XCloud"
    main_url: str = "https://xcloud.forum"
    
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        async with Session(verify=False) as session:
            resp = await session.get(url)
            doc = session.parse_html(resp.text)
            direct_btn = next((a for a in doc.css("div.vd a.btn-primary") if "Generate Direct" in a.text()), None)
            if not direct_btn: return
            links_resp = await session.get(fix_url(direct_btn.attributes.get("href"), self.main_url))
            links_doc = session.parse_html(links_resp.text)
            iframe = links_doc.css_first("iframe")
            if iframe: callback(ExtractorLink(self.name, self.name, iframe.attributes.get("src"), url, 0))
            for link in links_doc.css("h2 a.btn"):
                callback(ExtractorLink(self.name, self.name, fix_url(link.attributes.get("href"), self.main_url), url, 0))

class XcloudC(Xcloud): main_url = "https://xcloud.click"
