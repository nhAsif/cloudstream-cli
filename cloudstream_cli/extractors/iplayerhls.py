from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile

class Iplayerhls(ExtractorApi):
    name: str = "Iplayerhls"
    main_url: str = "https://iplayerhls.com"
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        from ..orchestrator import load_extractor
        await load_extractor(url, referer, callback, subtitle_callback)
