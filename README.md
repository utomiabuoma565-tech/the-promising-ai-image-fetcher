# The Promising AI Image Fetcher

A small remote MCP server for Claude. Its only job is to fetch a **direct public image URL** and return the original image bytes as MCP image content. It does not create ZIP files and does not crawl webpages.

## What it supports

- Direct public `http://` and `https://` image links
- Redirects to the final image URL
- PNG, JPEG, GIF, and WebP
- Original image bytes (no resizing or recompression)
- 20 MB per-image limit
- Blocks private/local network destinations

## Deploy on Render

1. Create a GitHub repository and upload every file in this folder.
2. In Render, choose **New → Blueprint** and connect that repository.
3. Render reads `render.yaml` and creates the web service.
4. Wait for deployment to finish. Your service URL will look like `https://YOUR-SERVICE.onrender.com`.
5. The MCP endpoint is normally `https://YOUR-SERVICE.onrender.com/mcp`.

Free Render services may sleep when inactive, so the first request after inactivity can take a little time.

## Connect to Claude Web

In Claude, open **Settings → Connectors → Add custom connector** (the exact labels can vary by account/UI). Give it the name `The Promising AI Image Fetcher` and use the MCP server URL:

`https://YOUR-SERVICE.onrender.com/mcp`

Complete the connection flow. If Claude asks for authentication, this starter does not implement user authentication; do not expose it publicly for sensitive/private image sources. Only use public image URLs.

## Use it

Ask Claude to use `fetch_image` on each direct image URL you provide. The tool returns the image itself as MCP image content, not just a URL.

Example instruction:

"Use The Promising AI Image Fetcher to retrieve each of these direct image URLs. After receiving the image content, create one ZIP containing the original image files. Keep the original file quality and report any URLs that fail."

## Important limitations and testing

- This starter accepts only links that return an image directly. It will reject ordinary webpages containing embedded images.
- The MCP protocol supports image content, but whether Claude's current connector UI passes that content through in a way that lets Claude package the original binary bytes into a ZIP must be tested. Image understanding/display is not necessarily the same as binary-file access.
- This starter has not yet been deployed or tested against your specific image links. Some hosts block automated requests, require cookies/login, or use anti-bot protection.
- For production use, add authentication, rate limiting, robust DNS pinning/SSRF protection, and tests before exposing the service broadly.
