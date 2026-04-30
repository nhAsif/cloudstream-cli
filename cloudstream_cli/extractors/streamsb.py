import re
import random
from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile
from ..network import Session
from ..utils import M3u8Helper

class StreamSB(ExtractorApi):
    name: str = "StreamSB"
    main_url: str = "https://watchsb.com"
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

    async def get_url(
        self,
        url: str,
        referer: Optional[str],
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> None:
        async with Session() as session:
            regex_id = r"(embed-[a-zA-Z\d]{0,8}[a-zA-Z\d_-]+|/e/[a-zA-Z\d]{0,8}[a-zA-Z\d_-]+)"
            match = re.search(regex_id, url)
            if not match: return
                
            id_str = match.group(1).replace("embed-", "").replace("/e/", "")
            encoded_id = self.encode_id(id_str)
            master = f"{self.main_url}/375664356a494546326c4b797c7c6e756577776778623171737/{encoded_id}"
            headers = {"watchsb": "sbstream", "Referer": url, "User-Agent": session.client.headers["User-Agent"]}
            response = await session.get(master.lower(), headers=headers)
            try:
                data = response.json()
                stream_data = data.get("stream_data", {})
                file_url = stream_data.get("file")
                if file_url:
                    links = await M3u8Helper.generate_m3u8(self.name, file_url, url, headers=headers, name=self.name)
                    for link in links: callback(link)
                subs = stream_data.get("subs", [])
                for sub in subs:
                    label = sub.get("label")
                    sub_file = sub.get("file")
                    if sub_file: subtitle_callback(SubtitleFile(url=sub_file, lang=label or "Unknown"))
            except Exception: pass

    def encode_id(self, id_str: str) -> str:
        code = f"{self.create_hash_table()}||{id_str}||{self.create_hash_table()}||streamsb"
        return "".join([hex(ord(c))[2:] for c in code])

    def create_hash_table(self) -> str:
        return "".join([random.choice(self.alphabet) for _ in range(12)])

# Subclasses
class Sblona(StreamSB): name = "Sblona"; main_url = "https://sblona.com"
class Sbrapid(StreamSB): name = "Sbrapid"; main_url = "https://sbrapid.com"
class Sbspeed(StreamSB): name = "Sbspeed"; main_url = "https://sbspeed.com"
