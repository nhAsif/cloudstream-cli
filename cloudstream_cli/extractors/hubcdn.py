import re
from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile
from ..network import Session
from ..utils import base64_decode

class HUBCDN(ExtractorApi):
    name: str = "HUBCDN"
    main_url: str = "https://hubcdn.one"
    
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        async with Session(verify=False) as session:
            resp = await session.get(url)
            doc = session.parse_html(resp.text)
            script = doc.css_first("script:contains('var reurl')")
            if not script: return
            match = re.search(r'reurl\s*=\s*"([^"]+)"', script.text())
            if not match: return
            encoded = match.group(1).split("?r=")[-1]
            decoded = base64_decode(encoded).split("link=")[-1]
            if decoded: callback(ExtractorLink(self.name, self.name, decoded, url, 0))
