from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile
from ..network import Session

class Plextream(ExtractorApi):
    name: str = "Plextream"
    main_url: str = "https://plextream.work"
    
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        async with Session(verify=False) as session:
            resp = await session.get(url, headers={"Referer": referer} if referer else None)
            doc = session.parse_html(resp.text)
            for btn in doc.css(".menu-card button"):
                onclick = btn.attributes.get("onclick", "")
                video_url = onclick.split("changeServer('")[-1].split("'")[0]
                if video_url:
                    from ..orchestrator import load_extractor
                    await load_extractor(video_url, url, callback, subtitle_callback)
