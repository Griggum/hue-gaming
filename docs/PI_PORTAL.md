# Pi profile portal on k3s

## Architecture

The gaming PC runs WoW OCR and writes directly to Hue. `hue_core` contains the
scene schema, five logical light positions, ambient engine, Hue transport and
generic game-event mappings. `wow_hue` owns the OCR detector and WoW location
adapter. `hue_portal` is an independent web service: no OCR, desktop capture,
game installation or gaming PC connection is required on the Pi.

The Pi's `/data/library.json` is authoritative. A library has a schema version,
server-managed revision, reusable scenes, and games whose events reference scene
IDs. Names and map IDs are scoped per game. Physical light assignments and Hue
credentials are local to each controller, never synchronized to game clients.

The seed contains all 98 existing WoW profiles and nine Valheim examples extracted
from this repository's Valheim specification. Valheim supports preset selection
and event-name lookup; automatic Valheim biome detection is not implemented.
Adding another game requires scenes and event mappings, not changes to the portal.

`hue-sync` polls in a separate process and atomically replaces a validated cache.
Failed requests, invalid profiles and unsupported schemas leave the previous
cache untouched. WoW takes an immutable snapshot at startup and validates it
against its local subzone registries. If unavailable or incompatible, it falls
back to the bundled WoW YAML. Start a new game-client session to use a newly
synchronized revision. No gameplay operation calls or waits for the Pi.

Pi and PC lighting are independent writers to Hue. Stop Pi playback before running
game lighting; stop the game client before playing a preset from your phone.
The Stop button stops only Pi updates and leaves lights at their current state.
Restarting the Pi service also stops playback; it never automatically resumes.

## Build and publish with GitHub Actions

`.github/workflows/container.yml` tests changes and, on pushes to `master`, version
tags such as `v0.1.0`, or a manual run on `master`, builds a native ARM64 image.
The workflow audits server dependencies, scans the completed image for OS/Python
HIGH/CRITICAL vulnerabilities and secrets, and smoke-tests its restricted runtime.
Only a successful candidate is published to `ghcr.io/griggum/hue-gaming`.
PRs run tests and the dependency audit without publishing.

The primary tag is `sha-FULL_COMMIT_SHA`; version-tag builds also publish the Git
tag, such as `v0.1.0`. Set the deployment image to that tag or the published digest.
There is no automatic Pi deployment or mutable `latest` tag. A registry package
may initially be private: make it public for anonymous Pi pulls, or configure an
`imagePullSecret`. The workflow uses GitHub's scoped `GITHUB_TOKEN`; no Hue or
portal credentials belong in Actions secrets or build arguments.

See [security review](SECURITY_REVIEW.md) for checks, exposure and limitations.

## Build the container manually

Use 64-bit Raspberry Pi OS with k3s. From the repository root, with Docker Buildx:

```sh
docker buildx build --platform linux/arm64 -t YOUR_REGISTRY/hue-portal:0.1.0 --push .
```

For both PC and Pi container hosts, use `--platform linux/amd64,linux/arm64`.
Only the `server` extra is installed in the image. OCR and ONNX are excluded.
Replace the image in `deploy/k3s/app.yaml` with the published tag (prefer a digest
for repeatable deployments). Configure an image pull secret if the registry is private.

For an offline/local image import, set the deployment image to `hue-portal:0.1.0`
and build on the Pi with
`docker build -t hue-portal:0.1.0 .`, then:

```sh
docker save hue-portal:0.1.0 -o hue-portal.tar
sudo k3s ctr images import hue-portal.tar
```

Import the image on every eligible node, or use a registry. The manifests assume
k3s's `local-path` storage provisioner. Keep one replica and `Recreate` updates:
the service is a single-writer file store and ambient scheduler.

## Deploy and open on your phone

Create a local `portal.env` file on your admin machine (do not commit it):

```dotenv
HUE_PORTAL_TOKEN=REPLACE_WITH_A_RANDOM_TOKEN_OF_AT_LEAST_24_CHARACTERS
HUE_BRIDGE_IP=192.168.1.123
HUE_USERNAME=YOUR_HUE_APPLICATION_KEY
HUE_PUBLIC_ORIGIN=https://hue.home.arpa
```

Generate a token with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
The portal token is separate from the Hue Bridge key. All profile reads, writes,
sync and control requests require it; the browser retains it only in memory.

```sh
kubectl apply -f deploy/k3s/namespace.yaml
kubectl -n hue create secret generic hue-credentials --from-env-file=portal.env
kubectl apply -f deploy/k3s/app.yaml
kubectl -n hue rollout status deployment/hue-portal
```

The service is internal (`ClusterIP`) by default, so deploying it does not open
an HTTP NodePort on every node. For phone access, configure your LAN DNS so
`hue.home.arpa` resolves to the Pi, and obtain a certificate your phone and PC trust
(for example, from your private CA). Replace that name in the secret's
`HUE_PUBLIC_ORIGIN` and `deploy/k3s/ingress.example.yaml` if needed.

```sh
kubectl -n hue create secret tls hue-portal-tls --cert=fullchain.pem --key=privkey.pem
kubectl apply -f deploy/k3s/ingress.example.yaml
```

The example uses k3s's Traefik ingress and its HTTPS-only `websecure` entrypoint.
Open `https://hue.home.arpa` on your phone and enter the portal token. Do not
bypass certificate warnings. Do not port-forward the ingress from your router
to the internet. Allow pod egress to the Hue Bridge on TCP 443.
`HUE_PUBLIC_ORIGIN` validates browser origins behind ingress; the application
continues to ignore spoofable forwarded headers. TLS terminates at ingress, so
traffic inside the cluster is HTTP. Cluster/node administrators remain trusted.

For a local administrative preview without configuring ingress, use
`kubectl -n hue port-forward service/hue-portal 8080:80` and visit
`http://localhost:8080`. If `HUE_PUBLIC_ORIGIN` is set to the HTTPS hostname, use
that hostname through ingress for mutations; the origin check intentionally
rejects other browser origins. Plain HTTP with real tokens over Wi-Fi is not the
recommended deployment path.

Under **Pi light positions**, read the bridge lights and assign the five positions.
Choose a preset to apply once, or enable **Keep ambience moving** for continuous
motion. Edit palettes and brightness through **Edit**. Add games or change event
routes under **Game mappings & library backup**. Saves reject dangling references,
duplicate aliases, invalid colors and conflicting browser revisions.

TLS verification for the Hue bridge is enabled by default. Mount a trusted CA
bundle and set `HUE_CA_FILE` to its container path. To explicitly trust your local
bridge's self-signed certificate instead:

```sh
kubectl -n hue set env deployment/hue-portal HUE_INSECURE=true
```

Make the same change in your deployment manifest to retain it on later applies.
The portal starts without bridge access so profile editing and sync still work
during a Hue outage. Playback errors appear in the portal. No credentials are
returned through its API. `/healthz` and `/readyz` are unauthenticated probes.

## Gaming PC setup and offline operation

```powershell
uv sync --extra gaming --group dev
$env:HUE_PORTAL_TOKEN = "YOUR_PORTAL_TOKEN"
uv run --no-sync hue-sync --server https://hue.home.arpa
# Keep this in a separate terminal, or schedule it at sign-in:
uv run --no-sync hue-sync --server https://hue.home.arpa --watch --interval 60
```

For a private CA, add `--ca-file C:\path\home-ca.pem` to each sync command.
The certificate must match the portal hostname. The phone must also trust that CA.

`config/app.yaml` now reads `profiles.cache.json` when valid. Existing `.env`,
`lights.yaml`, calibration and subzone registries stay local. The old commands
continue to work:

```powershell
uv run --no-sync wow-hue validate
uv run --no-sync wow-hue --insecure auto
uv run --no-sync hue-client --game valheim meadows --dry-run
uv run --no-sync hue-client --game valheim --insecure --ambient meadows
```

`hue-client` reads the same cache and controls Hue directly. Without a scene name
it lists presets; `--game GAME EVENT` resolves a game's event name to a scene.
Game adapters can use `Library.resolve()` with their own local detectors.

Without any Pi synchronization, WoW works from its existing bundled profiles.
To use the generic client before deploying the Pi, copy `config/library.seed.json`
to `config/profiles.cache.json`. Subsequent sync replaces that bootstrap copy.
Changes to the legacy YAML are fallback-only after a cache is configured. Edit
authoritative profiles on the Pi. To migrate a customized legacy catalog explicitly:

```powershell
uv run --no-sync hue-import-wow config/profiles.yaml custom-library.json
```

Import its scenes/mappings through the portal's full-library editor, retaining the
current revision. The importer refuses to overwrite an existing output file.

## Persistence, updates and backups

The PVC holds `library.json` and `lights.yaml`. The seed is copied only on the very
first start, and corrupt authoritative data fails startup instead of reseeding.
Image updates never overwrite profiles. Revision checking returns HTTP 409 when
another editor saved first; reload and reapply your changes.

Download a library backup from the portal. Also back up the PVC's `lights.yaml`
and keep credentials in your secret manager. Restore a library using the portal
editor with its current revision, or stop the deployment and restore the PVC files.
Deleting the PVC may delete the Pi's authoritative data. `local-path` storage is
node-local and does not provide replication or automatic disk-failure recovery.

## Local development

```powershell
uv sync --extra gaming --extra server --group dev
$env:HUE_PORTAL_TOKEN = "LOCAL_DEVELOPMENT_TOKEN_AT_LEAST_24_CHARS"
uv run --no-sync hue-portal
```

Open `http://localhost:8080`. Data defaults to ignored `data/`. Override it with
`HUE_DATA_DIR`, and the first-start library with `HUE_SEED_FILE`. The package also
supports a server-only install: `pip install '.[server]'`. Run the server from
the repository root or provide an absolute `HUE_SEED_FILE`.

Run `uv run --no-sync pytest` and `uv run --no-sync ruff check src tests` after
installing both extras. Deployment validation on actual ARM64 hardware and real
Hue lights is separate from the automated mock-bridge tests.
