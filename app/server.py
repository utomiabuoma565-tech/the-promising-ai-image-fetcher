"""The Promising AI Image Fetcher - remote MCP server.

Fetches a direct public image URL and returns the image bytes as MCP image
content. It does not scrape web pages, save files, or create ZIP archives.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urljoin, urlparse

import httpx
from mcp.server.fastmcp import FastMCP, Image


SERVER_NAME = "The Promising AI Image Fetcher"
PORT = int(os.getenv("PORT", "8000"))
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MiB per image
MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 45.0
ALLOWED_MIME_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/webp": "webp",
    "image/gif": "gif",
}

# In MCP SDK v1, HTTP bind settings belong on FastMCP(...), not run().
# Pinning mcp<2 in requirements.txt preserves this API.
mcp = FastMCP(
    SERVER_NAME,
    host="0.0.0.0",
    port=PORT,
    stateless_http=True,
)


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only public HTTP or HTTPS image URLs are supported.")
    if not parsed.hostname:
        raise ValueError("The URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded usernames or passwords are not supported.")

    host = parsed.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            records = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = list({ipaddress.ip_address(record[4][0]) for record in records})
        except socket.gaierror as exc:
            raise ValueError(f"Could not resolve the image host: {host}") from exc

    if not addresses:
        raise ValueError("The image host did not resolve to an IP address.")
    for address in addresses:
        if not address.is_global:
            raise ValueError("For safety, URLs resolving to private, local, or reserved IP addresses are blocked.")
    return url


def _detect_image(content_type: str, data: bytes) -> tuple[str, str]:
    mime = content_type.split(";", 1)[0].strip().lower()
    signatures = {
        "png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpeg": data.startswith(b"\xff\xd8\xff"),
        "gif": data.startswith((b"GIF87a", b"GIF89a")),
        "webp": len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
    }
    extension_by_mime = ALLOWED_MIME_TYPES
    if mime not in extension_by_mime:
        # Some hosts use application/octet-stream; identify by file signature.
        for extension, matches in signatures.items():
            if matches:
                mime = next(key for key, value in extension_by_mime.items() if value == extension)
                break
        else:
            raise ValueError(f"Unsupported image type: {mime or 'unknown'}.")
    extension = extension_by_mime[mime]
    if not signatures[extension]:
        raise ValueError("The URL did not return a valid image file matching its content type.")
    return mime, extension


async def _download_image(url: str) -> tuple[bytes, str, str]:
    current_url = url
    headers = {"User-Agent": "ThePromisingAI-ImageFetcher/1.0", "Accept": "image/*"}

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        headers=headers,
    ) as client:
        for redirect_number in range(MAX_REDIRECTS + 1):
            _validate_public_url(current_url)
            async with client.stream("GET", current_url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if redirect_number >= MAX_REDIRECTS:
                        raise ValueError("The image URL redirected too many times.")
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("The image host returned a redirect without a destination.")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_IMAGE_BYTES:
                    raise ValueError("The image is larger than the 20 MiB limit.")

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise ValueError("The image is larger than the 20 MiB limit.")
                    chunks.append(chunk)

                data = b"".join(chunks)
                if not data:
                    raise ValueError("The image URL returned an empty response.")
                mime, extension = _detect_image(response.headers.get("content-type", ""), data)
                return data, mime, extension

    raise ValueError("Could not download the image.")


@mcp.tool()
async def fetch_image(url: str) -> Image:
    """Fetch one direct public image URL and return its original image bytes.

    Supported formats: PNG, JPEG, WebP, and GIF. Maximum size: 20 MiB.
    Provide a direct image-file URL, not a webpage containing an image.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("Please provide a direct image URL.")
    data, mime, extension = await _download_image(url.strip())
    return Image(data=data, format=extension)


if __name__ == "__main__":
    # SDK v1 takes host/port/stateless_http in FastMCP(...).
    # Do not pass host or port to run(); that caused the original deploy error.
    mcp.run(transport="streamable-http")
