from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile

class Autoembed(ExtractorApi):
    name: str = "Autoembed"
    main_url: str = "https://player.autoembed.cc"
    
    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        callback(ExtractorLink(
            source=self.name,
            name=self.name,
            url=url,
            referer=referer,
            quality=0
        ))
