import re
from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile, ExtractorLinkType
from ..network import Session
from ..utils import get_and_unpack

class MixDrop(ExtractorApi):
    name: str = "MixDrop"
    main_url: str = "https://mixdrop.co"
    src_regex = r"wurl.*?=.*?\"(.*?)\";"

    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        async with Session() as session:
            embed_url = url.replace("/f/", "/e/")
            response = await session.get(embed_url)
            unpacked_text = get_and_unpack(response.text)
            
            match = re.search(self.src_regex, unpacked_text)
            if match:
                link = match.group(1)
                if link.startswith("//"):
                    link = f"https:{link}"
                
                callback(ExtractorLink(
                    source=self.name,
                    name=self.name,
                    url=link,
                    referer=embed_url,
                    quality=0,
                    type=ExtractorLinkType.VIDEO
                ))

class MixDropPs(MixDrop): main_url = "https://mixdrop.ps"
class Mdy(MixDrop): main_url = "https://mdy48tn97.com"
class MxDropTo(MixDrop): main_url = "https://mxdrop.to"
