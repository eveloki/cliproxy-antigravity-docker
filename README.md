# CLIProxyAPI + Antigravity Docker

**English** | [简体中文](README_CN.md)

A stable CPA distribution with the official Antigravity CLI and a bundled CLI executor plugin.
The default image layout matches `eceasy/cli-proxy-api`, so an existing local-file CPA deployment
can keep its Compose file and replace the image name.

> [!WARNING]
> **Do not install, update or reinstall `cliproxy-antigravity` through the management panel's plugin store,
> even if the panel offers an update.** This image bundles a patched plugin required for CPA v8 routing
> and SSE compatibility. A store binary can replace the active patched plugin and bring back
> `503 auth_not_found`. Update this plugin **only by upgrading this project's Docker image**.
> The warning applies to `cliproxy-antigravity`; see the explanation and recovery steps below.

- CPA and plugin follow the latest stable upstream releases through image builds, checked every 30 minutes; plugin compatibility patches and tests run before publication.
- Official CLI is pinned to `1.2.12` with a verified SHA256.
- Default test model: `gemini-3.8-flash`; plugin API model: `agy/gemini-3.8-flash`.
- Fixed tags include CPA, plugin, CLI and packaging versions; see [Releases](https://github.com/eveloki/cliproxy-antigravity-docker/releases) for published versions.
- Published platform: `linux/amd64`. ARM64 and Docker Desktop are not separately validated.

## Replace an existing CPA image

In your **existing deployment directory**, change only:

```yaml
image: ghcr.io/eveloki/cliproxy-antigravity-docker:latest
```

Then recreate the service:

```bash
docker compose pull cli-proxy-api
docker compose up -d --no-build cli-proxy-api
```

Keep your existing service name, port mappings, config, auth files, plugin files and data.
[compose.compat.yaml](compose.compat.yaml) illustrates the five-mount layout:

```yaml
services:
  cli-proxy-api:
    image: ghcr.io/eveloki/cliproxy-antigravity-docker:latest
    pull_policy: always
    container_name: cli-proxy-api
    ports:
      - "127.0.0.1:8317:8317"
    volumes:
      - ./config.yaml:/CLIProxyAPI/config.yaml
      - ./auths:/root/.cli-proxy-api
      - ./logs:/CLIProxyAPI/logs
      - ./plugins:/CLIProxyAPI/plugins
      - ./data:/CLIProxyAPI/data
    restart: unless-stopped
```

This file expects your real `config.yaml` to exist. Do not copy it into an unrelated directory:
relative mounts would then point to different data. Existing configuration is not rewritten by
our initialization scripts, and existing client keys are retained. CPA's own config-save behavior
still applies. A single-file bind can be read; upstream atomic config saves may require a directory mount.

The image defaults to root, `HOME=/root`, `WORKDIR=/CLIProxyAPI`, and `CMD ["./CLIProxyAPI"]`.
`./CLIProxyAPI`, native flags such as `-config`, and shell commands are accepted by the entrypoint.
Tini, plugin preparation and health checks remain distribution additions; this is not a byte-identical
upstream image. Existing native CPA credentials continue to serve their corresponding providers.
Third-party plugins still need to be compatible with the selected CPA version and Linux ABI.

## Enable the official Antigravity CLI route

Replacing the image preserves your CPA configuration. It **does not enable a plugin you disabled**,
convert CPA OAuth JSON into official CLI credentials, or change management-panel settings.

To use the bundled plugin, merge this into your existing `plugins` section, preserving other plugins:

```yaml
plugins:
  enabled: true
  dir: /CLIProxyAPI/plugins
  configs:
    cliproxy-antigravity:
      enabled: true
      binary_path: /usr/local/bin/agy
      workdir: /CLIProxyAPI/data/agy-workspace
      print_timeout: 30m
      dangerously_skip_permissions: false
      sandbox: false
      reasoning_effort: high
```

```bash
docker compose restart cli-proxy-api
# Official Google sign-in; no tokens are filled in by this project.
docker compose run --rm --no-build cli-proxy-api login
docker compose restart cli-proxy-api
# Display your CPA client key locally, not a Google credential.
docker compose exec cli-proxy-api python3 /opt/cliproxy/scripts/runtime_config.py key
# These live checks consume account quota.
docker compose exec cli-proxy-api /opt/cliproxy/scripts/doctor.sh
docker compose exec cli-proxy-api python3 /opt/cliproxy/scripts/smoke.py --tools
```

Use Base URL `http://127.0.0.1:8317/v1` and model `agy/gemini-3.8-flash`.
The prefix selects the CLI plugin instead of CPA's native Antigravity provider.
Add `--stream` to smoke for text SSE checks; run it separately from `--tools`.
The maintained test model is in `scripts/test-model.txt`; missing models fail without fallback.

Only the agy child process uses `HOME=/root/.cli-proxy-api/agy-home` by default.
This preserves official CLI state under your existing `./auths/agy-home` mount, separate from CPA's
native JSON files. No extra mount is required for the standard layout. Override `AGY_HOME` with a
persistent container directory for custom layouts or pre-existing official CLI state. CPA's HOME
remains `/root`; the wrapper never copies or converts account tokens.

The executable remains at `/opt/agy/agy`; it is not hidden by the auth or plugin mounts.
CLI auto-update is disabled. The `GEMINI_FORCE_FILE_STORAGE=true` compatibility setting remains
based on upstream reports, not a guaranteed keyring contract for every environment.

## Plugin installation and persisted data

### Why the bundled plugin must not be updated from the store

This project does more than bundle three upstream binaries. At image build time it applies the
[disclosed compatibility patch](compat/README.md) to upstream `cliproxy-antigravity` v0.1.3.
The current patched plugin identifies itself as **`0.1.3+cpa8-route1`**. CPA source is unchanged.

| Fix | Why it is needed |
| --- | --- |
| CPA v8 executor routing | Adds the `model_router` capability and `model.route` handler. Nonempty `agy/*` names return `Handled: true, TargetKind: self`, sending requests to the plugin's CLI executor. The unpatched v0.1.3 plugin lacks this route; with no matching CPA provider auth, requests fail with `503 auth_not_found` before agy runs. |
| SSE framing | Sends bare JSON chunks over the plugin ABI. CPA adds `data:` and the final `[DONE]`, avoiding duplicate `data: data: ...` framing and terminal markers. |

Client API-key validation remains in CPA, and Google authentication remains in the official CLI.
The patch does not fabricate provider credentials or take over bare model names/native provider routes.

The plugin store distributes upstream binaries, not this image's patched build. Installing one can
hot-reload the **same plugin ID** from another path, such as
`linux/amd64/cliproxy-antigravity-v0.1.3.so`, and retire the bundled `cliproxy-antigravity.so`.
The bundled file may still exist on disk while the unpatched store copy is active.
**A panel update badge is not proof of compatibility with this distribution.**

The startup checksum marker only manages the seeded file at its own path. It neither locks the
active plugin version nor prevents store installation or hot replacement. Store copies persist in
the plugin volume, so restarting or pulling a new image alone may not restore the patched plugin.

**Supported update path:** let this repository track upstream releases, apply the patch and run its
build/integration checks, then pull the resulting image and recreate the service. Follow the Compose
update commands above for your service name. Do not separately replace this plugin's `.so` with a
store/downloaded upstream binary. Keep this restriction until this project explicitly documents a
tested upstream replacement that no longer needs the patch.

If the store copy has already taken over:

1. Check the active plugin path/version in CPA load or hot-reload logs and the configured `plugins.dir`.
2. Back up and move only the conflicting unpatched `cliproxy-antigravity` binaries **outside the entire
   scanned plugin directory tree**, including architecture subdirectories. A backup subdirectory inside
   `plugins.dir` can still be scanned. Preserve unrelated plugins, config, credentials and data.
3. Retain the bundled managed copy; if that same file was overwritten, back up and move that conflicting
   copy out too, allowing startup to seed the image's patched library. Restart the affected service.
4. Confirm the **active** loaded version is `0.1.3+cpa8-route1` for the current release, then explicitly
   run an inference check. A model list containing `agy/*` alone does not prove routing works.

### Seeding and persistence

When the Antigravity plugin is enabled, startup copies its bundled library from
`/opt/cliproxy/bundled-plugins` into the configured writable plugin directory.
This works even when a bind mount initially hides all image files in `/CLIProxyAPI/plugins`.

- Other plugin files and their settings are preserved.
- A checksum marker identifies libraries installed by this distribution; only unchanged managed
  copies are upgraded. A different existing library or a user-modified copy is retained with a warning.
- An existing user-managed `cliproxy-antigravity.so` will therefore not be silently replaced by our
  patched build. Back it up and remove that file explicitly if you want the bundled version seeded.
- In the default root layout, the plugin store can write to the plugin mount. Management routes and
  credentials remain controlled by your config; startup does not enable the management panel.
  This writable store support does **not** permit replacing the bundled `cliproxy-antigravity` plugin.
- Keep plugin databases under the mounted `/CLIProxyAPI/data`, using each plugin's own data-path setting.
  This distribution does not move existing databases or rewrite third-party plugin options.

The bundled plugin includes the disclosed [CPA route/SSE compatibility patch](compat/README.md).
CPA source itself is not modified. Configuration-format compatibility does not guarantee every
third-party plugin is compatible with every automatically updated CPA release.

## Existing non-root deployments from this repository

`compose.yaml` retains the earlier named volumes and service name `cliproxy`. **Update that Compose
file together with the image**: it now explicitly selects UID/GID `10001:10001`, `HOME=/home/cliproxy`,
`AGY_HOME=/home/cliproxy`, `CPA_CONFIG=/config/config.yaml` and the previous working directory.
This prevents the new root image defaults from changing ownership or using a different login directory.
Do not switch to `compose.compat.yaml` merely to upgrade an existing named-volume deployment.

Use `v8.0.8-0.1.3-agy1.2.12-r3` or later when upgrading RC-era volumes. Those volumes may lack
`/home/cliproxy/plugins`; startup now creates the target of the old `/opt/cliproxy/plugins` symlink
as UID 10001. No host-side mkdir/chown or config edit is required. The earlier 8.0.8 r1/r2 images
missed this migration case. CI now creates volumes with the actual 8.0.6 RC image, then tests
upgrade, recreation and rollback with synthetic state, including unchanged file contents and ownership.

```bash
cd /www/cliproxy-antigravity-docker
git pull --ff-only
# Keep existing .env settings; change IMAGE from :rc to :latest if necessary.
[ -f .env ] || cp .env.example .env
docker compose pull
docker compose up -d --no-build
# First login only; skip if the persisted session is valid.
docker compose run --rm --no-build cliproxy login
docker compose restart cliproxy
docker compose exec cliproxy python3 /opt/cliproxy/scripts/runtime_config.py key
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools
```

| Setting | Existing CPA compatibility layout | Repository Compose layout |
| --- | --- | --- |
| User / CPA HOME | root / `/root` | 10001 / `/home/cliproxy` |
| Configuration | `/CLIProxyAPI/config.yaml` | `/config/config.yaml` |
| CPA credentials | `/root/.cli-proxy-api` | `/home/cliproxy/.cli-proxy-api` |
| Official CLI HOME | `/root/.cli-proxy-api/agy-home` | `/home/cliproxy` |
| Plugins | configured path, normally `/CLIProxyAPI/plugins` | `/home/cliproxy/plugins`; old `/opt/cliproxy/plugins` points there |
| Data | `/CLIProxyAPI/data` host bind | select a path inside the persisted HOME |

The repository template generates a private client key only if config is missing. Existing keys
are not rotated. Helpers support both legacy flat fields and v8 sections, including custom HTTP ports;
explicit `-config` / `--config` wins over `CPA_CONFIG`. Health probes use the runtime config path.
Repeated native `-config` flags use the last value; parsing stops at `--` or a positional argument.
`./CLIProxyAPI -help` and `./CLIProxyAPI discover ...` run directly without config initialization.
For local HTTPS health probes, certificate verification is skipped; live smoke uses normal TLS verification.
Native remote config backends, arbitrary custom entrypoints and every OAuth callback workflow are not
part of the five-mount compatibility test; preserve the relevant upstream settings and port mappings.

`docker compose down` preserves named volumes; `down -v` deletes them. Preserve the Compose project
name, credentials and config when upgrading. Never upload account credentials or volume backups to the repo.

## Releases and verification

Fixed tags use `v<CPA>-<plugin>-agy<CLI>-r<revision>` and are never overwritten by the workflow.
The management panel's build time is the UTC compilation time of the bundled CPA binary.
When Docker reuses that binary from its build cache, its original compilation time is retained.
`stable` and `latest` point to the same successfully published digest. Old RC and experimental tags
are retained. Use a fixed tag or digest to control upgrades; pulling a new image does not update an
already running container until you recreate it.

Main pushes and checks at minute 17/47 resolve stable CPA/plugin releases, build and test candidates,
record exact input SHAs, then publish GHCR and a GitHub Release. The official CLI stays pinned.
Failed builds/tests leave the previous aliases intact. Manual publication is available in Actions →
**Stable container release**. Go/base images track version series, so builds are not promised to be byte reproducible.

The owner confirmed `gemini-3.8-flash` live availability on 2026-10-01. CI checks the real CLI's offline
startup, synthetic JSON/SSE routing, native credential enumeration, read-only legacy config, writable
plugin/data mounts and recreation persistence. CI uses no Google credentials and does not make live
Google inference requests. See [validation records](docs/TESTING.md) for evidence and remaining scope.

## Sources and licenses

This distribution packages three upstream projects:

| Upstream | Role |
| --- | --- |
| [router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | API proxy server; follows stable releases. |
| [adeebahmad01/cliproxy-antigravity](https://github.com/adeebahmad01/cliproxy-antigravity) | Antigravity CLI executor plugin; follows stable releases with the disclosed compatibility patch. |
| [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli) | Official Antigravity CLI; bundled at a pinned version with SHA256 verification. |

See [upstream records](docs/UPSTREAM.md), `upstream-versions.json` and
[third-party notices](THIRD_PARTY_NOTICES.md). Packaging code is MIT; Google's CLI and other dependencies
retain their own terms. This project is not affiliated with Google or either upstream project.
