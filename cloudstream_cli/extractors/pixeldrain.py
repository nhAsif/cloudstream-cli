from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile

class PixelDrain(ExtractorApi):
    name: str = "PixelDrain"
    main_url: str = "https://pixeldrain.com"
    
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        file_id = url.split("/")[-1]
        callback(ExtractorLink(self.name, self.name, f"https://pixeldrain.com/api/file/{file_id}?download", url, 0))

class PixelDrainDev(PixelDrain): main_url = "https://pixeldrain.dev"
