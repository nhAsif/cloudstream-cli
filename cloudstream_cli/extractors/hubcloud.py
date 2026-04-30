import re
from typing import Optional, Callable
from ..base import ExtractorApi
from ..models import ExtractorLink, SubtitleFile
from ..network import Session

class HubCloud(ExtractorApi):
    name: str = "Hub-Cloud"
    main_url: str = "https://hubcloud.foo"
    
    async def get_url(self, url: str, referer: Optional[str], callback: Callable[[ExtractorLink], None], subtitle_callback: Callable[[SubtitleFile], None]):
        async with Session(verify=False) as session:
            ref = referer or ""
            if "hubcloud.php" in url:
                real_url = url
            else:
                resp = await session.get(url)
                if resp.status_code != 200: return
                parser = session.parse_html(resp.text)
                raw = parser.css_first("#download")
                if not raw: return
                href = raw.attributes.get("href", "")
                if href.startswith("http"):
                    real_url = href
                else:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    real_url = f"{base.rstrip('/')}/{href.lstrip('/')}"
            
            resp = await session.get(real_url)
            if resp.status_code != 200: return
            document = session.parse_html(resp.text)
            size_el = document.css_first("i#size")
            size = size_el.text().strip() if size_el else ""
            header_el = document.css_first("div.card-header")
            header = header_el.text().strip() if header_el else ""
            quality = self.get_index_quality(header)
            label_extras = ""
            if header: label_extras += f"[{header}]"
            if size: label_extras += f"[{size}]"
            
            for element in document.css("a.btn"):
                link = element.attributes.get("href", "")
                text = element.text().lower()
                if "fsl server" in text:
                    callback(ExtractorLink(f"{ref} [FSL Server]", f"{ref} [FSL Server] {label_extras}", link, real_url, quality))
                elif "download file" in text:
                    callback(ExtractorLink(ref or self.name, f"{ref or self.name} {label_extras}", link, real_url, quality))
                elif "buzzserver" in text:
                    buzz_resp = await session.get(f"{link}/download", headers={"Referer": link}, allow_redirects=False)
                    dlink = buzz_resp.headers.get("hx-redirect") or buzz_resp.headers.get("HX-Redirect")
                    if dlink: callback(ExtractorLink(f"{ref} [BuzzServer]", f"{ref} [BuzzServer] {label_extras}", dlink, link, quality))
                elif any(x in text for x in ["pixeldra", "pixelserver", "pixel server", "pixeldrain"]):
                    from urllib.parse import urlparse
                    parsed = urlparse(link)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    final_url = link if "download" in link else f"{base}/api/file/{link.split('/')[-1]}?download"
                    callback(ExtractorLink(f"{ref} Pixeldrain", f"{ref} Pixeldrain {label_extras}", final_url, link, quality))
                elif "s3 server" in text:
                    callback(ExtractorLink(f"{ref} [S3 Server]", f"{ref} [S3 Server] {label_extras}", link, real_url, quality))
                elif "fslv2" in text:
                    callback(ExtractorLink(f"{ref} [FSLv2]", f"{ref} [FSLv2] {label_extras}", link, real_url, quality))
                elif "mega server" in text:
                    callback(ExtractorLink(f"{ref} [Mega Server]", f"{ref} [Mega Server] {label_extras}", link, real_url, quality))
                elif "pdl server" in text:
                    callback(ExtractorLink(f"{ref} [PDL Server]", f"{ref} [PDL Server] {label_extras}", link, real_url, quality))
                else:
                    from ..orchestrator import load_extractor
                    await load_extractor(link, real_url, callback, subtitle_callback)

    def get_index_quality(self, str_val: str) -> int:
        match = re.search(r"(\d{3,4})[pP]", str_val)
        return int(match.group(1)) if match else 0

class HubDrive(HubCloud): name = "Hubdrive"; main_url = "https://hubdrive.space"
class KatDrive(HubCloud): name = "KatDrive"; main_url = "https://katdrive.info"
class NewsDrive(HubCloud): name = "NewsDrive"; main_url = "https://newsdrive.in"
class GdFlix(HubCloud): name = "GdFlix"; main_url = "https://gdflix.cfd"
