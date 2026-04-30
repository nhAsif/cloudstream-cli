from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Union

class TvType(Enum):
    Movie = 1
    AnimeMovie = 2
    TvSeries = 3
    Cartoon = 4
    Anime = 5
    OVA = 6
    Torrent = 7
    Documentary = 8
    AsianDrama = 9
    Live = 10
    NSFW = 11
    Others = 12
    Music = 13
    AudioBook = 14
    CustomMedia = 15
    Audio = 16
    Podcast = 17
    Video = 18

class SearchQuality(Enum):
    Cam = 1
    CamRip = 2
    HdCam = 3
    Telesync = 4 # TS
    WorkPrint = 5
    Telecine = 6 # TC
    HQ = 7
    HD = 8
    HDR = 9
    BlueRay = 10
    DVD = 11
    SD = 12
    FourK = 13
    UHD = 14
    SDR = 15
    WebRip = 16

class DubStatus(Enum):
    None_ = -1
    Dubbed = 1
    Subbed = 0

class ShowStatus(Enum):
    Completed = 0
    Ongoing = 1

class ExtractorLinkType(Enum):
    VIDEO = "VIDEO"
    M3U8 = "M3U8"
    DASH = "DASH"
    TORRENT = "TORRENT"
    MAGNET = "MAGNET"

@dataclass
class SearchResponse:
    name: str
    url: str
    apiName: str
    type: Optional[TvType] = None
    posterUrl: Optional[str] = None
    posterHeaders: Optional[Dict[str, str]] = None
    id: Optional[int] = None
    quality: Optional[SearchQuality] = None
    score: Optional[int] = None

@dataclass
class HomePageList:
    name: str
    list: List[SearchResponse]
    isHorizontalImages: bool = False

@dataclass
class HomePageResponse:
    items: List[HomePageList]
    hasNext: bool = False

@dataclass
class MainPageRequest:
    name: str
    data: str
    isHorizontalImages: bool = False

@dataclass
class MovieSearchResponse(SearchResponse):
    year: Optional[int] = None

@dataclass
class TvSeriesSearchResponse(SearchResponse):
    year: Optional[int] = None
    episodes: Optional[int] = None

@dataclass
class AnimeSearchResponse(SearchResponse):
    year: Optional[int] = None
    dubStatus: Optional[List[DubStatus]] = None
    otherName: Optional[str] = None
    episodes: Dict[DubStatus, int] = field(default_factory=dict)

@dataclass
class TrailerData:
    extractorUrl: str
    referer: Optional[str]
    raw: bool
    headers: Dict[str, str] = field(default_factory=dict)

@dataclass
class Actor:
    name: str
    image: Optional[str] = None

@dataclass
class ActorData:
    actor: Actor
    role: Optional[int] = None # ActorRole enum in Kotlin
    roleString: Optional[str] = None
    voiceActor: Optional[Actor] = None

@dataclass
class Episode:
    data: str
    name: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    posterUrl: Optional[str] = None
    score: Optional[int] = None
    description: Optional[str] = None
    date: Optional[int] = None # Long in Kotlin, timestamp
    runTime: Optional[int] = None

@dataclass
class LoadResponse:
    name: str
    url: str
    apiName: str
    type: TvType
    uniqueUrl: str
    posterUrl: Optional[str] = None
    year: Optional[int] = None
    plot: Optional[str] = None
    score: Optional[int] = None
    tags: Optional[List[str]] = None
    duration: Optional[int] = None
    trailers: List[TrailerData] = field(default_factory=list)
    recommendations: Optional[List[SearchResponse]] = None
    actors: Optional[List[ActorData]] = None
    comingSoon: bool = False
    syncData: Dict[str, str] = field(default_factory=dict)
    posterHeaders: Optional[Dict[str, str]] = None
    backgroundPosterUrl: Optional[str] = None
    logoUrl: Optional[str] = None
    contentRating: Optional[str] = None

@dataclass
class MovieLoadResponse(LoadResponse):
    dataUrl: str = ""

@dataclass
class TvSeriesLoadResponse(LoadResponse):
    episodes: List[Episode] = field(default_factory=list)
    showStatus: Optional[ShowStatus] = None

@dataclass
class AnimeLoadResponse(LoadResponse):
    episodes: Dict[DubStatus, List[Episode]] = field(default_factory=dict)
    showStatus: Optional[ShowStatus] = None
    engName: Optional[str] = None
    japName: Optional[str] = None
    synonyms: Optional[List[str]] = None

@dataclass
class TorrentLoadResponse(LoadResponse):
    magnet: Optional[str] = None
    torrent: Optional[str] = None

@dataclass
class ExtractorLink:
    source: str
    name: str
    url: str
    referer: str
    quality: int
    type: ExtractorLinkType = ExtractorLinkType.VIDEO
    headers: Dict[str, str] = field(default_factory=dict)
    extractorData: Optional[str] = None

@dataclass
class SubtitleFile:
    url: str
    lang: str
    headers: Optional[Dict[str, str]] = None
