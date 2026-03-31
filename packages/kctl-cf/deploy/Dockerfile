FROM cloudflare/cloudflared:latest

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD cloudflared tunnel info || exit 1

ENTRYPOINT ["cloudflared", "tunnel", "--no-autoupdate", "run"]
