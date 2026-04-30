import shutil
import subprocess
import logging
from typing import List, Optional
from .models import ExtractorLink, SubtitleFile

logger = logging.getLogger(__name__)

class Player:
    def __init__(self):
        self.vlc_path = shutil.which("vlc")
        self.mpv_path = shutil.which("mpv")

    def play(self, link: ExtractorLink, subs: List[SubtitleFile]):
        if self.mpv_path:
            self._play_mpv(link, subs)
        elif self.vlc_path:
            self._play_vlc(link, subs)
        else:
            print("No supported player found (VLC or MPV). Please install one.")

    def _play_mpv(self, link: ExtractorLink, subs: List[SubtitleFile]):
        cmd = [self.mpv_path]
        
        # Referrer
        if link.referer:
            cmd.append(f'--referrer={link.referer}')
        
        # Headers
        headers = link.headers.copy()
        if link.referer and "Referer" not in headers:
            headers["Referer"] = link.referer
        
        if headers:
            header_fields = ",".join([f"{k}: {v}" for k, v in headers.items()])
            cmd.append(f'--http-header-fields={header_fields}')
        
        # Subtitles
        for sub in subs:
            cmd.append(f'--sub-file={sub.url}')
            
        cmd.append(link.url)
        
        print(f"Launching MPV: {' '.join(cmd)}")
        try:
            subprocess.run(cmd)
        except Exception as e:
            print(f"Error launching MPV: {e}")

    def _play_vlc(self, link: ExtractorLink, subs: List[SubtitleFile]):
        cmd = [self.vlc_path]
        
        if link.referer:
            cmd.append(f'--http-referrer={link.referer}')
            
        # VLC doesn't have a direct way to pass arbitrary headers via CLI easily 
        # like MPV, but it does have some specific flags. 
        # For now, we follow the requirement: vlc --http-referrer="<ref>" "<url>"
        
        # Subtitles in VLC CLI can be tricky if they are remote URLs. 
        # VLC's --sub-file usually expects local files. 
        # The requirement didn't explicitly ask for subtitles in VLC, only MPV.
        
        cmd.append(link.url)
        
        print(f"Launching VLC: {' '.join(cmd)}")
        try:
            subprocess.run(cmd)
        except Exception as e:
            print(f"Error launching VLC: {e}")
