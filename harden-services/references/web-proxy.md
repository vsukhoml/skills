# Reverse proxy and TLS hardening (nginx, Caddy)

The reverse proxy is usually the only public service on the host. Make it boring.
It should terminate TLS, enforce limits, hide internals, and pass a minimal,
trusted view of the client to the apps behind it.

## TLS

- **Protocols:** TLS 1.2 + 1.3, using Mozilla's "intermediate" profile (or
  "modern", TLS 1.3 only, when every client supports it). Caddy's defaults
  already comply.
- **Certificates are getting shorter-lived.** CA/B Forum ballot SC-081 limits
  public TLS certs to 200 days from March 2026, 100 days from March 2027, and
  47 days from March 2029. Let's Encrypt also offers 6-day certs. Fully
  automated ACME renewal is mandatory, and so is **monitoring expiry**
  independently.
- **OCSP stapling.** Let's Encrypt ended its OCSP service in 2025, so its certs
  carry no OCSP URL. Remove `ssl_stapling` for LE certs; nginx otherwise warns
  on every reload. Keep stapling only for CAs that still run OCSP.
- **Certificate Transparency** publishes every hostname you get a cert for.
  Internal hostnames on public certs are discoverable. Use a wildcard or an
  internal CA if that matters (it is not access control either way).
- `ssl_session_tickets off` (nginx), unless you rotate ticket keys, to preserve
  forward secrecy. Caddy rotates them automatically.

## nginx

```nginx
# http {} level
server_tokens off;
client_max_body_size 10m;                 # per-location overrides for uploads
client_body_timeout 15s;                  # slowloris
client_header_timeout 15s;
keepalive_timeout 30s;
send_timeout 15s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_conn_zone $binary_remote_addr zone=perip:10m;

ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers off;            # TLS 1.3 + modern clients choose well
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;

# Catch-all: scanners hitting the bare IP or an unknown Host get nothing,
# not your first vhost (which leaks which apps exist).
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    listen 443 ssl default_server;
    listen [::]:443 ssl default_server;
    ssl_reject_handshake on;               # nginx >= 1.19.4: no cert needed for the catch-all
    return 444;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name app.example.com;
    ssl_certificate     /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;   # add preload only deliberately
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Content-Security-Policy "frame-ancestors 'none'" always;               # app-specific CSP belongs to the app

    limit_conn perip 50;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;   # overwrite, don't append client-supplied values
    proxy_set_header X-Forwarded-Proto $scheme;

    location ~ /\.(?!well-known/) { deny all; }   # .git, .env, .htpasswd, editor swap files
    location ~* \.(bak|old|orig|sql|tar|gz|zip)$ { deny all; }

    location /login { limit_req zone=login burst=5 nodelay; proxy_pass http://127.0.0.1:8080; }
    location / {
        proxy_pass http://127.0.0.1:8080;      # upstream on loopback/unix socket, never public
    }
}
```

- **nginx `add_header` & `proxy_set_header` inheritance footgun:** Any child
  `location {}` block that defines even a single `add_header` (such as
  `add_header Cache-Control ...`) **silently drops all `server`-level
  `add_header` directives** (`HSTS`, `X-Content-Type-Options`, `CSP`,
  `Referrer-Policy`) for that location — and the same rule applies to
  `proxy_set_header`! Put shared security/proxy headers in
  `/etc/nginx/snippets/` and `include` them in every `location` that adds custom
  headers — or enforce security headers centrally in the application middleware.
- **Application-layer HTTP & parser hardening:** Reverse-proxy headers do not
  replace app-layer CSRF, hash-allowlisted CSP, BREACH-safe compression scoping,
  pre-KDF rate limiting, or fuzzing custom request/body parsers (`harden-build`).
- **Real client IP behind a CDN or load balancer.** Use `set_real_ip_from` only
  for the CDN's published ranges, with `real_ip_header CF-Connecting-IP` (or
  `X-Forwarded-For` + `real_ip_recursive on`). Trusting `X-Forwarded-For` from
  anyone lets attackers spoof their IP past rate limits and allow-lists.
- **Origin behind Cloudflare or another CDN.** Lock the origin's 80/443 to the
  CDN's IP ranges in the firewall, or use authenticated origin pulls or a
  tunnel. Otherwise attackers find the origin IP (CT logs, historical DNS) and
  bypass the WAF.
- Run under the systemd sandbox (`harden-host` §6). nginx needs
  `CAP_NET_BIND_SERVICE` and write access to its cache, log and pid paths.

## Caddy

- Defaults are good: automatic HTTPS, TLS 1.2+, HTTP→HTTPS redirects, and OCSP
  handled automatically.
- **Admin API.** Caddy's admin endpoint (`localhost:2019`) is unauthenticated
  and can rewrite the whole config. Keep it on localhost or a unix socket
  (`admin unix//run/caddy/admin.sock`), or `admin off` if you reload via
  restarts. The socket's directory must be writable by Caddy:
  `RuntimeDirectory=caddy` in its systemd unit, or a `tmpfs: /run/caddy` on a
  read-only container. Otherwise Caddy fails at start, and `caddy validate`
  won't tell you. Never publish 2019 from a container, and never run Caddy with
  `network_mode: host` alongside untrusted local users without that change.
- Headers and limits:
  ```caddy
  {
      admin unix//run/caddy/admin.sock
      servers {
          timeouts {
              read_body 15s
              read_header 10s
              idle 60s
          }
      }
  }
  app.example.com {
      header {
          Strict-Transport-Security "max-age=31536000; includeSubDomains"
          X-Content-Type-Options nosniff
          Referrer-Policy strict-origin-when-cross-origin
          -Server
      }
      # Go's RE2 has no lookahead: express "dotfiles except .well-known" as two matchers
      @hidden {
          path_regexp /\.
          not path /.well-known/*
      }
      respond @hidden 404
      request_body {
          max_size 10MB
      }
      reverse_proxy 127.0.0.1:8080
  }
  ```
- Rate limiting needs a plugin (`caddy-ratelimit`). Plugins mean a custom build,
  which is a supply-chain decision: pin it via `xcaddy` versions and checksums.

## Verification

```sh
testssl.sh --fast app.example.com                 # protocols, ciphers, HSTS, cert chain
curl -sI https://app.example.com | grep -iE 'strict-transport|server:|x-content-type'
curl -sk https://<public-ip>/ -o /dev/null -w '%{http_code}\n'    # catch-all: connection reset / 000
curl -s -o /dev/null -w '%{http_code}\n' https://app.example.com/.git/config   # 403/404
curl -s -o /dev/null -w '%{http_code}\n' https://app.example.com/.env          # 403/404
```
