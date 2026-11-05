import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

mcp = FastMCP("The Promising AI Image Fetcher", stateless_http=True)

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_REDIRECTS = 6
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# Formats that Claude/MCP clients commonly support as image content.
SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", "png"),
    "image/jpeg": (b"\xff\xd8\xff", "jpeg"),
    "image/gif": ((b"GIF87a", b"GIF89a"), "gif"),
    "image/webp": (None, "webp"),
}

def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Please provide a complete http:// or https:// image URL.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not supported.")
    host = parsed.hostname
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("The image host could not be resolved.") from exc
    if not addresses:
        raise ValueError("The image host could not be resolved.")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("For safety, links to private, local, or reserved network addresses are blocked.")

def identify_image(data: bytes, content_type: str) -> str:
    content_type = content_type.split(";", 1)[0].strip().lower()
    if content_type == "image/webp":
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "webp"
        raise ValueError("The response was labelled WebP but did not contain a valid WebP signature.")
    spec = SIGNATURES.get(content_type)
    if spec is None:
        raise ValueError(f"Unsupported image type: {content_type or 'unknown'}. Supported types: PNG, JPEG, GIF, and WebP.")
    signature, fmt = spec
    if isinstance(signature, tuple):
        valid = data.startswith(signature)
    else:
        valid = data.startswith(signature)
    if not valid:
        raise ValueError("The server response did not contain a valid image file.")
    return fmt

@mcp.tool()
async def fetch_image(url: str) -> Image:
    """Fetch one direct public image URL and return the original image bytes to Claude as MCP image content. Does not scrape webpages."""
    current_url = url.strip()
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": "PromisingAI-ImageFetcher/1.0"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current_url)
            async with client.stream("GET", current_url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("The image server redirected without providing a destination.")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not content_type.lower().startswith("image/"):
                    raise ValueError(
                        f"This URL returned {content_type or 'an unknown content type'}, not an image. "
                        "Please provide a direct link that opens the image itself."
                    )

                declared_length = response.headers.get("content-length")
                if declared_length:
                    try:
                        if int(declared_length) > MAX_IMAGE_BYTES:
                            raise ValueError("The image is larger than the 20 MB limit.")
                    except ValueError as exc:
                        if "limit" in str(exc):
                            raise

                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_IMAGE_BYTES:
                        raise ValueError("The image is larger than the 20 MB limit.")

                image_bytes = bytes(chunks)
                image_format = identify_image(image_bytes, content_type)
                return Image(data=image_bytes, format=image_format)

    raise ValueError("The image URL redirected too many times.")

if __name__ == "__main__":
    import os
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
