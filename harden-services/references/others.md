# Other data stores, brokers, observability and admin UIs

Default-insecure is the norm in this list. Assume **no authentication by default**
until you have proven otherwise, and never expose any of these to the internet.

| Service | Default exposure trap | Must-do |
| --- | --- | --- |
| **Elasticsearch 8+/9** | Security (TLS + auth) is on by default since 8.0. Guides tell you to set `xpack.security.enabled: false` "to make it work". | Keep security on. Set `network.host` to loopback or a private address. Apps get API keys or roles with index-level privileges, never the `elastic` superuser. Kibana sits behind auth and is not public. |
| **OpenSearch** | The demo security config (`install_demo_configuration.sh`) uses publicly known demo certs and creds | Never use the demo config in production. Use your own CA and certs, set the admin password (`OPENSEARCH_INITIAL_ADMIN_PASSWORD`, required since 2.12), and set role mappings. |
| **Memcached** | No auth. UDP was the 2018 51,000× DDoS amplification vector. | `-l 127.0.0.1` (or private), `-U 0` (UDP off; the default since 1.5.6). Use SASL if it crosses hosts. Prefer a unix socket (`-s`). |
| **etcd** | Plaintext and no auth unless configured. It holds Kubernetes secrets. | `--client-cert-auth`, `--peer-client-cert-auth`, TLS on 2379/2380, firewalled to cluster members only |
| **RabbitMQ** | `guest` is restricted to loopback, so don't lift `loopback_users`. Management UI on 15672. **Erlang distribution (25672) + epmd (4369) + a known cookie = RCE.** | Per-app vhosts and users, TLS listeners. 15672/25672/4369 must never be public. Random `.erlang.cookie` with mode 400. |
| **Kafka** | PLAINTEXT listeners with no ACLs | SASL/SCRAM or mTLS, `allow.everyone.if.no.acl.found=false`, controller (KRaft) listeners internal only |
| **ClickHouse** | The `default` user. Older images allowed a passwordless `default` from anywhere. HTTP 8123 / native 9000. | Set a password or disable `default`. `<networks>` restricted to loopback or private. Per-app users with quotas. Ports not public. |
| **Qdrant / Weaviate / Chroma / Milvus** (vector DBs) | No auth unless configured. Bots hit a freshly started public Qdrant in under 2 minutes. | Qdrant: `service.api_key` + `read_only_api_key` (`QDRANT__SERVICE__API_KEY`). Others: enable their auth module. Internal network only. TLS if remote. |
| **Ollama / LLM inference servers** | 11434 with no auth. Model theft, prompt abuse, GPU cryptojacking. | Bind `127.0.0.1` (`OLLAMA_HOST`). Put an authenticating reverse proxy in front if remote access is needed. |
| **MinIO / S3-compatible** | Default root creds in quick-starts. Console on 9001. | Change root creds and use per-app access keys with bucket policies. No anonymous buckets. Console not public. TLS. |
| **InfluxDB / Prometheus / exporters** | Prometheus has no auth by default. Exporters (9100…) leak versions, processes and users. | Bind loopback/private. Prometheus `web.config.file` for TLS and basic auth. Scrape over a private network. |
| **Grafana** | `admin/admin` on first start, sign-up, anonymous access | Change admin on first start. `allow_sign_up=false`, `[auth.anonymous] enabled=false`. Use SSO if available. |
| **Docker registry (`registry:2`)** | No auth by default; anyone can push poisoned images | htpasswd or token auth + TLS, or a managed registry. Pull through a proxy cache. |
| **Admin UIs** (Portainer, Adminer, phpMyAdmin, pgAdmin, Jupyter, code-server, Jenkins, n8n, Dozzle, Netdata) | Credential stuffing; many are RCE-by-design once logged in (Jupyter, code-server, Portainer) | Never public. Reach them over WireGuard or SSH tunnel, or behind an SSO proxy (oauth2-proxy, Authelia, Authentik) with MFA. |
| **Postfix/Exim on non-mail hosts** | Listening on 0.0.0.0:25; open relay misconfigs | `inet_interfaces = loopback-only`. Relay through an authenticated smarthost. |
| **DNS resolvers** (unbound/dnsmasq/bind) | Open recursion means amplification attacks | `access-control` to own networks; listen on loopback or private |
| **NTP** (chrony) | Serving time publicly; mode 6/7 amplification (old ntpd) | chrony without `allow` serves no clients. `cmdport 0` if chronyc isn't needed remotely. |

## Universal verification for any service in this list

```sh
ss -tulpn | grep <port>                  # bind address: loopback or private only
nmap -Pn -p <port> <public-ip>           # from outside: filtered or closed (IPv4 and IPv6)
# then a no-credential request with the service's client must be refused, e.g.:
curl -s http://127.0.0.1:6333/collections    # Qdrant: 401/403 expected when api_key is set
```
