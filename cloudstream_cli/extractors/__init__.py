from typing import List
from ..base import ExtractorApi

from .streamsb import StreamSB, Sblona, Sbrapid, Sbspeed
from .hubcloud import HubCloud, HubDrive, KatDrive, NewsDrive, GdFlix
from .hubcdn import HUBCDN
from .xcloud import Xcloud, XcloudC
from .plextream import Plextream
from .streamwish import StreamwishHG
from .iplayerhls import Iplayerhls
from .rpmvid import Rpmvid
from .hdstream4u import HdStream4u
from .pixeldrain import PixelDrain, PixelDrainDev
from .videasy import Videasy
from .autoembed import Autoembed
from .mixdrop import MixDrop, MixDropPs, Mdy, MxDropTo

def get_extractors() -> List[ExtractorApi]:
    return [
        StreamSB(), Sblona(), Sbrapid(), Sbspeed(),
        HubCloud(), HubDrive(), KatDrive(), NewsDrive(), GdFlix(),
        HUBCDN(),
        Xcloud(), XcloudC(),
        Plextream(),
        StreamwishHG(),
        Iplayerhls(),
        Rpmvid(),
        HdStream4u(),
        PixelDrain(), PixelDrainDev(),
        Videasy(),
        Autoembed(),
        MixDrop(), MixDropPs(), Mdy(), MxDropTo()
    ]
