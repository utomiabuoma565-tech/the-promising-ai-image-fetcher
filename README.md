# The Promising AI Image Fetcher

A small remote MCP server for Claude-compatible MCP clients. It provides one tool:

- `fetch_image(url)` downloads a direct, publicly reachable image URL and returns the image as MCP image content.

It supports PNG, JPEG, WebP, and GIF. The per-image limit is 20 MiB. It follows up to five redirects and blocks URLs that resolve to private, local, or reserved IP addresses.

**This service only fetches and returns images. It does not scrape web pages, create ZIP files, or store downloads.** Claude would need to create any ZIP archive separately.

## Deploy on Render

1. Upload the contents of this folder to the root of a GitHub repository.
2. In Render, choose **New → Blueprint** and select that repository.
3. Select branch `main` and Blueprint file `render.yaml`.
4. Review the service and deploy it.
5. Wait until the web service status is **Live**. The MCP endpoint is the Render service URL followed by `/mcp`.

Render uses the `PORT` environment variable. The server binds to `0.0.0.0` and uses that port.

## Connect to an MCP client

Use the service endpoint:

`https://YOUR-RENDER-SERVICE.onrender.com/mcp`

The exact connection flow depends on the MCP client. Use the remote MCP / Streamable HTTP option.

## Important compatibility note

This project uses `mcp.server.fastmcp.FastMCP` from MCP SDK v1. The requirements file deliberately pins the dependency below v2 because v2 renamed/reworked this API. In SDK v1, `host`, `port`, and `stateless_http` are configured in the `FastMCP(...)` constructor; `run()` receives only the transport here. This avoids the `FastMCP.run() got an unexpected keyword argument 'host'` error.

## Important end-to-end limitation

The MCP tool returns an MCP **image content block**. A client may display or interpret that image without exposing the original binary bytes to the model's file-creation feature. Therefore, a successful Render deployment does **not** by itself prove that Claude can package the exact original downloaded bytes into a ZIP. Test that workflow in Claude before relying on it. This server does not create ZIP files.

## Security and operating notes

- This is intended for direct public image URLs, not private/authenticated image hosts.
- Do not add credentials or secrets to image URLs.
- The service is publicly reachable unless you add authentication or network restrictions. Avoid using it as a general-purpose proxy.
- DNS checks reduce SSRF risk but cannot guarantee protection against every DNS-rebinding or network-level edge case.
- Render's free service may spin down when idle, so the first request after inactivity can take longer.
