import re
import random
import json
from typing import Optional, List, Callable, Dict, Any
from .base import ExtractorApi
from .models import ExtractorLink, SubtitleFile, ExtractorLinkType
from .network import Session
from .utils import get_and_unpack, M3u8Helper, fix_url

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
            # Regex to extract ID
            regex_id = r"(embed-[a-zA-Z\d]{0,8}[a-zA-Z\d_-]+|/e/[a-zA-Z\d]{0,8}[a-zA-Z\d_-]+)"
            match = re.search(regex_id, url)
            if not match:
                return
                
            id_str = match.group(1).replace("embed-", "").replace("/e/", "")
            
            encoded_id = self.encode_id(id_str)
            master = f"{self.main_url}/375664356a494546326c4b797c7c6e756577776778623171737/{encoded_id}"
            
            headers = {
                "watchsb": "sbstream",
                "Referer": url,
                "User-Agent": session.client.headers["User-Agent"]
            }
            
            response = await session.get(master.lower(), headers=headers)
            try:
                data = response.json()
                stream_data = data.get("stream_data", {})
                file_url = stream_data.get("file")
                
                if file_url:
                    links = await M3u8Helper.generate_m3u8(
                        self.name,
                        file_url,
                        url,
                        headers=headers,
                        name=self.name
                    )
                    for link in links:
                        callback(link)
                        
                subs = stream_data.get("subs", [])
                for sub in subs:
                    label = sub.get("label")
                    sub_file = sub.get("file")
                    if sub_file:
                        subtitle_callback(SubtitleFile(url=sub_file, lang=label or "Unknown"))
                        
            except Exception as e:
                # print(f"Error parsing StreamSB response: {e}")
                pass

    def encode_id(self, id_str: str) -> str:
        code = f"{self.create_hash_table()}||{id_str}||{self.create_hash_table()}||streamsb"
        return "".join([hex(ord(c))[2:] for c in code])

    def create_hash_table(self) -> str:
        return "".join([random.choice(self.alphabet) for _ in range(12)])

# StreamSB Subclasses
class Sblona(StreamSB): name = "Sblona"; main_url = "https://sblona.com"
class Lvturbo(StreamSB): name = "Lvturbo"; main_url = "https://lvturbo.com"
class Sbrapid(StreamSB): name = "Sbrapid"; main_url = "https://sbrapid.com"
class Sbface(StreamSB): name = "Sbface"; main_url = "https://sbface.com"
class Sbsonic(StreamSB): name = "Sbsonic"; main_url = "https://sbsonic.com"
class Vidgomunimesb(StreamSB): main_url = "https://vidgomunimesb.xyz"
class Sbasian(StreamSB): name = "Sbasian"; main_url = "https://sbasian.pro"
class Sbnet(StreamSB): name = "Sbnet"; main_url = "https://sbnet.one"
class Keephealth(StreamSB): name = "Keephealth"; main_url = "https://keephealth.info"
class Sbspeed(StreamSB): name = "Sbspeed"; main_url = "https://sbspeed.com"
class Streamsss(StreamSB): main_url = "https://streamsss.net"
class Sbflix(StreamSB): name = "Sbflix"; main_url = "https://sbflix.xyz"
class Vidgomunime(StreamSB): main_url = "https://vidgomunime.xyz"
class Sbthe(StreamSB): main_url = "https://sbthe.com"
class Ssbstream(StreamSB): main_url = "https://ssbstream.net"
class SBfull(StreamSB): main_url = "https://sbfull.com"
class StreamSB1(StreamSB): main_url = "https://sbplay1.com"
class StreamSB2(StreamSB): main_url = "https://sbplay2.com"
class StreamSB3(StreamSB): main_url = "https://sbplay3.com"
class StreamSB4(StreamSB): main_url = "https://cloudemb.com"
class StreamSB5(StreamSB): main_url = "https://sbplay.org"
class StreamSB6(StreamSB): main_url = "https://embedsb.com"
class StreamSB7(StreamSB): main_url = "https://pelistop.co"
class StreamSB8(StreamSB): main_url = "https://streamsb.net"
class StreamSB9(StreamSB): main_url = "https://sbplay.one"
class StreamSB10(StreamSB): main_url = "https://sbplay2.xyz"
class StreamSB11(StreamSB): main_url = "https://sbbrisk.com"
class Sblongvu(StreamSB): main_url = "https://sblongvu.com"

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
            # Ensure we are using the embed URL
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
                    quality=0, # Unknown
                    type=ExtractorLinkType.VIDEO
                ))

# MixDrop Subclasses
class MixDropPs(MixDrop): main_url = "https://mixdrop.ps"
class Mdy(MixDrop): main_url = "https://mdy48tn97.com"
class MxDropTo(MixDrop): main_url = "https://mxdrop.to"
class MixDropSi(MixDrop): main_url = "https://mixdrop.si"
class MixDropBz(MixDrop): main_url = "https://mixdrop.bz"
class MixDropAg(MixDrop): main_url = "https://mixdrop.ag"
class MixDropCh(MixDrop): main_url = "https://mixdrop.ch"

# List of all extractor instances
extractor_apis: List[ExtractorApi] = [
    StreamSB(), Sblona(), Lvturbo(), Sbrapid(), Sbface(), Sbsonic(),
    Vidgomunimesb(), Sbasian(), Sbnet(), Keephealth(), Sbspeed(),
    Streamsss(), Sbflix(), Vidgomunime(), Sbthe(), Ssbstream(),
    SBfull(), StreamSB1(), StreamSB2(), StreamSB3(), StreamSB4(),
    StreamSB5(), StreamSB6(), StreamSB7(), StreamSB8(), StreamSB9(),
    StreamSB10(), StreamSB11(), Sblongvu(),
    MixDrop(), MixDropPs(), Mdy(), MxDropTo(), MixDropSi(),
    MixDropBz(), MixDropAg(), MixDropCh()
]

def get_extractors() -> List[ExtractorApi]:
    return extractor_apis
