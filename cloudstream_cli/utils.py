import base64
import re
import codecs
from typing import Optional, List, Dict, Any
from .network import Session

def fix_url(url: Optional[str], main_url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"{main_url.rstrip('/')}{url}"
    return f"{main_url.rstrip('/')}/{url}"

def base64_decode(data: str) -> str:
    try:
        # Add padding if needed
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return base64.b64decode(data).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def rot13(text: str) -> str:
    return codecs.encode(text, 'rot_13')

async def get_redirect_links(url: str, session: Optional[Session] = None) -> str:
    """
    Port of the getRedirectLinks utility found in multiple providers.
    """
    if session is None:
        from .orchestrator import get_manager
        session = get_manager().session

    try:
        resp = await session.get(url)
        doc = resp.text
        
        # Regex matching the s('o', '...') or ck('_wp_http_...', '...') patterns
        regex = r"s\('o','([A-Za-z0-9+/=]+)'|ck\('_wp_http_\d+','([^']+)'"
        matches = re.findall(regex, doc)
        
        combined = ""
        for m in matches:
            val = m[0] or m[1]
            if val:
                combined += val
        
        if not combined:
            return ""
            
        # Replicate: decodedString = base64Decode(pen(base64Decode(base64Decode(combinedString))))
        # base64Decode(combinedString)
        step1 = base64.b64decode(combined).decode('utf-8', errors='ignore')
        # base64Decode(step1)
        step2 = base64.b64decode(step1).decode('utf-8', errors='ignore')
        # pen (rot13)
        step3 = rot13(step2)
        # base64Decode
        decoded_json_str = base64.b64decode(step3).decode('utf-8', errors='ignore')
        
        import json
        data_json = json.loads(decoded_json_str)
        
        encoded_url = base64_decode(data_json.get("o", ""))
        
        if encoded_url:
            return encoded_url.strip()
            
        # blog_url + ?re= + encoded_data
        blog_url = data_json.get("blog_url", "").strip()
        data_param = base64_decode(data_json.get("data", "")).strip()
        
        if blog_url and data_param:
            direct_resp = await session.get(f"{blog_url}?re={data_param}")
            # Simplified: just return the body text as in Kotlin
            return direct_resp.text.strip()
            
    except Exception as e:
        print(f"Error in get_redirect_links: {e}")
        
    return ""

class JsUnpacker:
    def __init__(self, packed_js: str):
        self.packed_js = packed_js

    def detect(self) -> bool:
        return "p,a,c,k,e,d" in self.packed_js

    def unpack(self) -> str:
        # Ported logic for P.A.C.K.E.R. unpacking
        # Matches p,a,c,k,e,d pattern
        try:
            pattern = r"}\('(.*)',\s*(.*),\s*(.*),\s*'(.*)'.split\('|'\)"
            match = re.search(pattern, self.packed_js)
            if not match: return self.packed_js
            
            p, a, c, k = match.groups()
            a = int(a)
            c = int(c)
            k = k.split('|')
            
            def e(c):
                return ('' if c < a else e(int(c / a))) + \
                       (chr(c % a + 161) if c % a > 35 else str(int(c % a, 36)))

            while c > 0:
                c -= 1
                if k[c]:
                    self.packed_js = re.sub(r'\b' + e(c) + r'\b', k[c], self.packed_js)
            return self.packed_js
        except:
            return self.packed_js

def get_and_unpack(text: str) -> str:
    unpacker = JsUnpacker(text)
    if unpacker.detect():
        return unpacker.unpack()
    return text

class M3u8Helper:
    @staticmethod
    async def generate_m3u8(
        source: str,
        m3u8_url: str,
        referer: str,
        headers: Optional[Dict[str, str]] = None,
        name: str = "HLS"
    ) -> List[Any]: # List[ExtractorLink]
        from .models import ExtractorLink, ExtractorLinkType
        
        # Very basic HLS link generation
        # In a full implementation, we would parse the M3U8 for resolutions
        return [ExtractorLink(
            source=source,
            name=name,
            url=m3u8_url,
            referer=referer,
            quality=0,
            type=ExtractorLinkType.M3U8,
            headers=headers
        )]
