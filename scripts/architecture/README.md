# Architecture icon preparation

The logo resolver is vendored from [caru-ini/stack-diagram](https://github.com/caru-ini/stack-diagram/blob/main/skills/stack-diagram/scripts/fetch_icons.py), retrieved 2026-11-04. Its MIT notice is in `LICENSE-stack-diagram.txt`. Brand assets retain their own terms; the script's license does not license the logos.

Run the resolver locally to prepare an asset directory:

```powershell
uv run python scripts/architecture/fetch_icons.py output/architecture-icons nextjs hono neon clerk stripe
```

The directory includes the original image files and a `manifest.json` recording sources. The resolver supports explicit URLs and AWS, GCP, and Azure service selectors. It runs as a local preparation command, outside MCP request handling.

The architecture renderer currently accepts embedded raster icons. SVG support, manifest-driven icon selection, and the complete reference layout are still being integrated. The reference gallery is [stacks.caru.moe](https://stacks.caru.moe/).
