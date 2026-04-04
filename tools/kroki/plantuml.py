"""
PlantUML client library.

This library allows you to connect to a PlantUML server and render
PlantUML markup into PNG images.
"""

import logging
from typing import Dict, Optional, Tuple
from zlib import compress

import httpx

logger = logging.getLogger(__name__)


class PlantUMLError(Exception):
    """Error in processing."""


class PlantUMLConnectionError(PlantUMLError):
    """Error connecting or talking to PlantUML Server."""


class PlantUMLHTTPError(PlantUMLError):
    """Request to PlantUML server returned HTTP Error."""

    def __init__(self, response: httpx.Response, content: str) -> None:
        self.response = response
        self.content = content
        req = getattr(response, "request", None)
        self.url = req.url if req else "unknown URL"
        self.message = f"HTTP Error: {self.url} {response}"
        super().__init__(self.message)


class PlantUML:
    """Connection to a PlantUML server with optional authentication."""

    def __init__(
        self,
        url: str,
        basic_auth: Optional[Dict] = None,
        form_auth: Optional[Dict] = None,
        http_opts: Optional[Dict] = None,
        request_opts: Optional[Dict] = None,
    ) -> None:
        """Initialize the PlantUML client.

        Args:
            url: URL to the PlantUML server image CGI
            basic_auth: Dictionary containing username and password for basic HTTP auth
            form_auth: Dictionary for cookie based webform login authentication
            http_opts: Extra options for the HTTP client
            request_opts: Extra options for HTTP requests
        """
        if basic_auth is None:
            basic_auth = {}
        if form_auth is None:
            form_auth = {}
        if http_opts is None:
            http_opts = {}
        if request_opts is None:
            request_opts = {}

        self.url = url
        self.request_opts = request_opts

        # Determine auth type
        self.auth_type = None
        if basic_auth:
            self.auth_type = "basic_auth"
        elif form_auth:
            self.auth_type = "form_auth"

        self.auth = basic_auth or form_auth or None

        # Create HTTP client without proxies argument
        self.client = httpx.Client(
            **{k: v for k, v in http_opts.items() if k != "proxies"}
        )

        # Configure authentication
        if self.auth_type == "basic_auth":
            auth = self.auth
            assert auth is not None
            self.client.auth = (auth["username"], auth["password"])
        elif self.auth_type == "form_auth":
            auth = self.auth
            assert auth is not None
            if "url" not in auth:
                raise PlantUMLError(
                    "The form_auth option 'url' must be provided and point to the login url."
                )
            if "body" not in auth:
                raise PlantUMLError(
                    "The form_auth option 'body' must be provided and include "
                    "a dictionary with the form elements required to log in."
                )

            login_url = auth["url"]
            body = auth["body"]
            method = auth.get("method", "POST")
            headers = auth.get(
                "headers", {"Content-type": "application/x-www-form-urlencoded"}
            )

            try:
                response = self.client.request(
                    method, login_url, headers=headers, data=body
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise PlantUMLConnectionError(f"Error authenticating: {str(e)}")

            self.request_opts["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in response.cookies.items()
            )

    def get_url(self, plantuml_text):
        """Return the server URL for the image."""
        # PlantUML server expects ~1 prefix for 6-bit (HUFFMAN) encoding
        encoded = self.deflate_and_encode(plantuml_text)
        return f"{self.url}/~1{encoded}"

    def process(self, plantuml_text: str):
        """Process the plantuml text and return the URL and content."""
        url = self.get_url(plantuml_text)
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return url, plantuml_text
        except httpx.HTTPError as e:
            resp = getattr(e, "response", None)
            if resp is None:
                raise
            content = getattr(resp, "text", "") or (
                resp.content.decode("utf-8", errors="replace") if resp.content else ""
            )
            raise PlantUMLHTTPError(resp, content)

    def deflate_and_encode(self, plantuml_text):
        """Compress and encode the plantuml text."""
        zlibbed_str = compress(plantuml_text.encode("utf-8"))
        compressed_string = zlibbed_str[2:-4]
        return self.encode(compressed_string)

    def encode(self, data: bytes):
        """Encode the plantuml data."""
        res = ""
        for i in range(0, len(data), 3):
            if i + 2 == len(data):
                res += self._encode3bytes(data[i], data[i + 1], 0)
            elif i + 1 == len(data):
                res += self._encode3bytes(data[i], 0, 0)
            else:
                res += self._encode3bytes(data[i], data[i + 1], data[i + 2])
        return res

    def _encode3bytes(self, b1: int, b2: int, b3: int):
        """Encode 3 bytes into 4 characters."""
        c1 = b1 >> 2
        c2 = ((b1 & 0x3) << 4) | (b2 >> 4)
        c3 = ((b2 & 0xF) << 2) | (b3 >> 6)
        c4 = b3 & 0x3F
        res = ""
        res += self._encode6bit(c1 & 0x3F)
        res += self._encode6bit(c2 & 0x3F)
        res += self._encode6bit(c3 & 0x3F)
        res += self._encode6bit(c4 & 0x3F)
        return res

    def _encode6bit(self, b):
        """Encode 6 bits into a single character."""
        if b < 10:
            return chr(48 + b)
        b -= 10
        if b < 26:
            return chr(65 + b)
        b -= 26
        if b < 26:
            return chr(97 + b)
        b -= 26
        if b == 0:
            return "-"
        return "_" if b == 1 else "?"

    def generate_image_from_string(self, plantuml_text: str) -> Tuple[str, str, str]:
        """Generate an image from plantuml markup and return URLs.

        Args:
            plantuml_text: The PlantUML markup text

        Returns:
            Tuple of (image_url, content_text, playground_url)

        Raises:
            PlantUMLHTTPError: If there was an error processing the diagram
        """
        try:
            url, content = self.process(plantuml_text)
            encoded_part = url.split("/")[-1]
            playground = f"https://www.plantuml.com/plantuml/uml/{encoded_part}"
            return url, content, playground
        except PlantUMLHTTPError as e:
            raise PlantUMLHTTPError(e.response, str(e))
