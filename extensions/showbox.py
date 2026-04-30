import json
import base64
import hashlib
import ssl
import tempfile
import os
from typing import List, Optional, Callable, Dict, Any
from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad
import httpx

from cloudstream_cli.base import MainAPI
from cloudstream_cli.models import (
    TvType, SearchResponse, LoadResponse, MovieLoadResponse, TvSeriesLoadResponse,
    Episode, ActorData, Actor, TrailerData, ExtractorLink, SubtitleFile,
    SearchQuality
)
from cloudstream_cli.network import Session

class ShowBoxProvider(MainAPI):
    name: str = "ShowBox"
    main_url: str = "https://www.showbox.media/"
    lang: str = "en"
    supported_types = {TvType.Movie, TvType.TvSeries, TvType.Anime}

    # API Constants (Base64 decoded from Kotlin)
    IV = b"vEiphTn!"
    KEY = b"123d6cedf626dy54233aa1w6"
    APP_KEY = b"moviebox"
    APP_ID = b"com.tdo.showbox"
    FIRST_API = "https://showboxssl.shegu.net/api/api_client/"
    SECOND_API = "https://showboxapissl.stsoso.com/api/api_client/"
    
    CLIENT_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIEFTCCAv2gAwIBAgIUCrILmXOevO03gUhhbEhG/wZb2uAwDQYJKoZIhvcNAQEL
BQAwgagxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQH
Ew1TYW4gRnJhbmNpc2NvMRkwFwYDVQQKExBDbG91ZGZsYXJlLCBJbmMuMRswGQYD
VQQLExJ3d3cuY2xvdWRmbGFyZS5jb20xNDAyBgNVBAMTK01hbmFnZWQgQ0EgM2Q0
ZDQ4ZTQ2ZmI3MGM1NzgxZmI0N2VhNzk4MjMxZDMwHhcNMjQwNjA0MDkxMTAwWhcN
MzkwNjAxMDkxMTAwWjAiMQswCQYDVQQGEwJVUzETMBEGA1UEAxMKQ2xvdWRmbGFy
ZTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAJhpMlr/+IatuBqpuZuA
6QvqdI2QiFb1UMVujb/xiaBC/vqJMlMenLSDysk8xd4fLeC+GC8AyWf1IMJIz6d9
rBjOhN4D+MxvgphufkdIVqs63SqKcrr/ZL0JaRpxxEg/pKqSjH55Ik71keB8tt0m
mQ76WK1swMydOAqn6DIKVAi7wF9acWyX/6Ly+cmxfueLDZvkLigXl3gMHbuoa5Y+
CadqKl2qlijhnvjpuEbAvyDyXWe838TUi0PYMMVuOu7PV4By2LINsm+gKv83od4k
RCSWTrLKlgfqneqnudMrqeWckNUHGVB+3Lruw1ebB/Rs4gJ59VhJYpbNmM2mYT0r
VQkCAwEAAaOBuzCBuDATBgNVHSUEDDAKBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAA
MB0GA1UdDgQWBBSF9Jkz4ZkbS5+LANO3YGWZRuX/PDAfBgNVHSMEGDAWgBTj01Q6
MJPAjpPqCEcv8rjxAUTO9jBTBgNVHR8ETDBKMEigRqBEhkJodHRwOi8vY3JsLmNs
b3VkZmxhcmUuY29tL2U1YTYzNzc5LTQ3NWQtNGI5OS04YzQxLTIwMjE5MmZhNjNj
ZC5jcmwwDQYJKoZIhvcNAQELBQADggEBALD+9MsfANm7fbzYH5/lXl07hwn2KSN8
PH7zxyo87ED62IL9U7YOnhb3rqLS1RXUzyHEmb9kzYgzKzzNrELdKH77vNk172Vk
iRQwGD0MZiYNERWhmmBtjV1oxllz74fL4+aZTYAespIbOekmFn9NZJ+XSdyF9RqS
fzDiz27GP5ZSHHI6xwdUP+a87N/RnfI4UwGxyXvPpHfoAZWjoXDqLKKwEL36/Sqi
nGcp970y0gnZ2zI2ehqivsF7BATMZqvU+LJKCH8NEE2bnbCJ6qlPHZWZFNKYWBOe
I1Crf0gNAWD/q3HKGMVZiyxlhU6SsQS4/08tDXXQjWYfl6i3oviexSk=
-----END CERTIFICATE-----"""

    CLIENT_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCYaTJa//iGrbga
qbmbgOkL6nSNkIhW9VDFbo2/8YmgQv76iTJTHpy0g8rJPMXeHy3gvhgvAMln9SDC
SM+nfawYzoTeA/jMb4KYbn5HSFarOt0qinK6/2S9CWkaccRIP6Sqkox+eSJO9ZHg
fLbdJpkO+litbMDMnTgKp+gyClQIu8BfWnFsl/+i8vnJsX7niw2b5C4oF5d4DB27
qGuWPgmnaipdqpYo4Z746bhGwL8g8l1nvN/E1ItD2DDFbjruz1eActiyDbJvoCr/
N6HeJEQklk6yypYH6p3qp7nTK6nlnJDVBxlQfty67sNXmwf0bOICefVYSWKWzZjN
pmE9K1UJAgMBAAECggEAQFvnxjKiJWkVPbkfJjHU91GtnxwB3sqfrYdmN0ANUE4K
MwydYikinj2q87iEi6wZ6PYM60hHRG1oRHKPsZgphJ4s0D3YIagS+0Bpdbtv0cW9
IBovoZR4WzUum1qgOqwZYmgZCM0pNjOPwr6XT6Ldbkw8BxvN/HmFcUZ/ECZ5XugW
cKqKoy0HSlxwXT4PUAgLVfL4KvWy4A4yJJF24zgRKE4QYveOR4nUFvoRdxhuAyYW
xsajItj6sc6Jyr9FJzdw5Ra9EFwcWFM4uDdjHoaQrjwKId9fkCA+9eUCERWKTxCR
P8mU4p2cAJYO+ME9fZfs8H2uqGNj13XUzoT6JzM8UwKBgQDUFZWcfmlgCM2BjU9c
8qhYjD2egT3qxWJLYSUTUZfdOGgB6lxTqnOhsy93xYmVInz6r9XEZsLVoQj/wcZk
p7y+MxjiWNcBcUmviwHee42fe6BQZHaYlAFtlAKNSiHumfq6AtXpZvkQZJWTSRyW
lI4LBEL6fSuqpk88EH9FXJbChwKBgQC3+F/1Qi3EoeohhWD+jMO0r8IblBd7jYbp
2zs17KQsCEyc1qyIaE+a8Ud8zUqsECKWBuSFsQ2qrR3jZW6DZOw8hmp1foYC+Jjr
C/BHyWsyYxrCoxpvSJMXCY6ulyFHjIZboopRVi/jgfowteMW6WyxvOMqVAqZtxRW
HyFbsa+/7wKBgQCGHRwd+SZjr01dZmHQcjaYwB5bNHlWE/nDlyvd2pQBNaE3zN8T
nU8/6tLSl50YLNYBpN22NBFzDEFnkj8F+bh2QlOzFuDnrZ8eHfZRnaoCNyg6jj0c
4UNB6v3uIPnyK3cM16wzy4Umo6SenfYxFsH4H3rHcg4B/OdQIVKKJzHC0wKBgQCj
QxhlX0WeqtJMzUE2pVVIlHF+Z/4u93ozLwts34USTosu5JRYublrl5QJfWY3LFqF
KbjDrEykmt1bYDijAn1jeSYg/xeOq2+JqB6klms7XBfzgyuCdrWSTDkDV7uA84SI
7cYySHpXPJH7iG7vdlevpCE0/0ApCgBSLW49IYMGoQKBgAxVRqAhLdA0RO+nTAC/
whOL5RGy5M2oXKfqNkzEt2k5og7xXY7ZoYTye5Byb3+wLpEJXW+V8FlfXk/u5ZI7
oFuZne+lYcCPMNDXdku6wKdf9gSnOSHOGMu8TvHcud4uIDYmFH5qabJL5GDoQi7Q
12XvK21e6GNOEaRRlTHz0qUB
-----END PRIVATE KEY-----"""

    def __init__(self, session: Optional[Session] = None):
        self._session = session or Session()
        self.token = self._random_token()
        self._ssl_context = self._create_ssl_context()

    def _random_token(self) -> str:
        import random
        chars = "0123456789abcdef"
        return "".join(random.choice(chars) for _ in range(32))

    def _create_ssl_context(self):
        ctx = ssl.create_default_context()
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as cert_file, \
             tempfile.NamedTemporaryFile(mode='w', delete=False) as key_file:
            cert_file.write(self.CLIENT_CERT_PEM)
            key_file.write(self.CLIENT_KEY_PEM)
            cert_path = cert_file.name
            key_path = key_file.name
        
        try:
            ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        finally:
            os.remove(cert_path)
            os.remove(key_path)
        return ctx

    def _encrypt(self, text: str) -> str:
        cipher = DES3.new(self.KEY, DES3.MODE_CBC, self.IV)
        encrypted = cipher.encrypt(pad(text.encode(), DES3.block_size))
        return base64.b64encode(encrypted).decode()

    def _md5(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    async def _query_api(self, query_dict: Dict[str, Any], use_alt: bool = False) -> Dict[str, Any]:
        query_str = json.dumps(query_dict, separators=(',', ':'))
        encrypted = self._encrypt(query_str)
        app_key_hash = self._md5(self.APP_KEY.decode())
        
        verify = self._md5(self._md5(self.APP_KEY.decode()) + self.KEY.decode() + encrypted)
        
        new_body = {
            "app_key": app_key_hash,
            "verify": verify,
            "encrypt_data": encrypted
        }
        base64_body = base64.b64encode(json.dumps(new_body, separators=(',', ':')).encode()).decode()
        
        payload = {
            "data": base64_body,
            "appid": "27",
            "platform": "android",
            "version": "131",
            "medium": "Website",
            "token": self.token
        }
        
        url = self.SECOND_API if use_alt else self.FIRST_API
        headers = {
            "Platform": "android",
            "Accept": "charset=utf-8",
            "User-Agent": "okhttp/3.12.6"
        }
        
        async with httpx.AsyncClient(verify=self._ssl_context) as client:
            resp = await client.post(url, data=payload, headers=headers)
            if resp.status_code != 200 and not use_alt:
                return await self._query_api(query_dict, use_alt=True)
            return resp.json()

    async def search(self, query: str, page: int = 1) -> Optional[List[SearchResponse]]:
        import time
        expiry = int(time.time() + 3600 * 12)
        api_query = {
            "childmode": "0",
            "app_version": "11.7",
            "module": "Search3",
            "channel": "Website",
            "page": str(page),
            "lang": "en",
            "type": "all",
            "keyword": query,
            "pagelimit": "20",
            "expired_date": str(expiry),
            "platform": "android",
            "appid": self.APP_ID.decode()
        }
        
        data = await self._query_api(api_query)
        results = []
        for item in data.get("data", []):
            box_type = item.get("box_type")
            results.append(SearchResponse(
                name=item.get("title"),
                url=json.dumps({"id": item.get("id") or item.get("mid"), "type": box_type}),
                apiName=self.name,
                type=TvType.TvSeries if box_type == 2 else TvType.Movie,
                posterUrl=item.get("poster") or item.get("poster_org")
            ))
        return results

    async def load(self, url: str) -> Optional[LoadResponse]:
        import time
        expiry = int(time.time() + 3600 * 12)
        try:
            load_data = json.loads(url)
        except:
            return None
            
        is_movie = load_data.get("type") == 1
        module = "Movie_detail" if is_movie else "TV_detail_1"
        id_key = "mid" if is_movie else "tid"
        
        api_query = {
            "childmode": "0",
            "uid": "",
            "app_version": "11.7",
            "appid": self.APP_ID.decode(),
            "module": module,
            "channel": "Website",
            id_key: str(load_data.get("id")),
            "lang": "en",
            "expired_date": str(expiry),
            "platform": "android"
        }
        
        if not is_movie:
            api_query["display_all"] = "1"
            
        data_resp = await self._query_api(api_query)
        data = data_resp.get("data")
        if not data: return None
        
        common = {
            "name": data.get("title"),
            "url": url,
            "apiName": self.name,
            "type": TvType.Movie if is_movie else TvType.TvSeries,
            "dataUrl": url,
            "posterUrl": data.get("poster") or data.get("poster_org"),
            "plot": data.get("description"),
            "year": data.get("year"),
            "score": int(float(data.get("imdb_rating", 0)) * 10) if data.get("imdb_rating") else None
        }
        
        if is_movie:
            return MovieLoadResponse(**common)
        else:
            episodes = []
            # For simplicity, we'd need another query for seasons/episodes if not in initial data
            # The Kotlin source shows it iterates over seasons
            return TvSeriesLoadResponse(**common, episodes=episodes)

    async def load_links(
        self,
        data: str,
        callback: Callable[[ExtractorLink], None],
        subtitle_callback: Callable[[SubtitleFile], None]
    ) -> bool:
        # ShowBox uses Febbox for links, which requires a specific token (Supertoken)
        # and complex extraction. This is a placeholder.
        return False
