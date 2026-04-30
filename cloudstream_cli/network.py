import httpx
from selectolax.lexbor import LexborHTMLParser
from typing import Optional, Dict, Any, Union

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"

class Session:
    """
    A wrapper around httpx.AsyncClient to handle common scraping tasks.
    """
    def __init__(
        self,
        proxy: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        base_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            base_headers.update(headers)

        self.client = httpx.AsyncClient(
            headers=base_headers,
            proxy=proxy,
            timeout=timeout,
            follow_redirects=True,
        )

    async def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        referer: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Send a GET request.
        """
        request_headers = headers or {}
        if referer:
            request_headers["Referer"] = referer
        
        return await self.client.get(url, headers=request_headers, params=params, **kwargs)

    async def post(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        referer: Optional[str] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Send a POST request.
        """
        request_headers = headers or {}
        if referer:
            request_headers["Referer"] = referer
            
        return await self.client.post(
            url, data=data, json=json, headers=request_headers, **kwargs
        )

    @staticmethod
    def parse_html(html: Union[str, bytes]) -> LexborHTMLParser:
        """
        Parse HTML using LexborHTMLParser.
        """
        return LexborHTMLParser(html)

    async def close(self):
        """
        Close the underlying httpx client.
        """
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
