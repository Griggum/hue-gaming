# Container and portal security review

Reviewed 2026-09-25. This is a source, packaging and dependency review, not a
penetration test or a guarantee that the image is vulnerability-free.

## Findings and fixes

| Finding | Resolution |
| --- | --- |
| Default HTTP NodePort exposed bearer tokens to LAN traffic observation and listened on cluster nodes | Default service is now ClusterIP. An HTTPS-only Traefik ingress example and certificate setup replace the plain HTTP phone-access instructions. |
| API bodies had no application size ceiling and were parsed before authentication | An ASGI guard authenticates first and caps streamed bodies at 8 MiB, including requests without Content-Length. |
| Validation errors could echo submitted values | Invalid API input receives a generic 422 response without submitted data. |
| Base image tags could change without review | Python and uv images are pinned to verified multi-architecture registry digests. Dependabot checks Docker and Actions updates weekly. |
| Broad source-directory inclusion could admit future non-code files | Docker context uses an allowlist for Python source, portal HTML/CSS/JS, project metadata, lockfile and the seed catalog. |

## Image contents and credentials

The Docker context excludes `.env`, `portal.env`, `.git`, local light mappings,
OCR calibration, downloaded profile caches, persistent portal data, logs, tests,
documentation and Kubernetes Secrets. Runtime copies only the installed Python
environment and the curated seed catalog from the build inputs. No credential
build arguments are used. Build tools and their caches remain in the builder.

A local comparison against credential values in the existing `.env` found zero
matches in the permitted image inputs. Values were neither printed nor sent to
an external scanner. This check is not a general proof that arbitrary secrets
could never be added to source files; CI also scans the finished image for secrets.

The public image intentionally contains the application code and curated WoW /
Valheim palettes. Your edited profiles and physical light assignments stay on
the Pi's PVC. Credentials are injected at runtime using a Kubernetes Secret.

## Exposed interfaces

- Container HTTP port: 8080. The default Kubernetes service is cluster-internal.
- Public routes: login page, three allowlisted static assets, `/healthz`, `/readyz`.
- Every `/api/` route requires the portal bearer token before body parsing.
- Bridge credentials are never returned by the API. The portal token stays in
  browser memory; it is not placed in URLs, cookies or localStorage.
- Browser requests carrying an Origin must match the configured HTTPS origin
  (or the direct origin during local development). No CORS policy grants access
  to other websites. Forwarded headers are not trusted.
- Interactive API docs, filesystem downloads and directory listings are disabled.
- Bridge connections use a private LAN IP, certificate verification by default,
  and ignore environment HTTP proxies. Sync does not follow redirects or use
  environment proxies.
- Hue TLS supports an explicitly provisioned CA bundle and Bridge ID for
  certificate-name verification, including CN-only Hue certificates. This is
  scoped to the Bridge client; it does not change system or portal trust. Invalid
  chains, expired certificates and name mismatches fail before credentials are
  sent. No automatic unverified connection or HTTP fallback is attempted.

The image runs as UID/GID 10001. The deployment drops all Linux capabilities,
disables privilege escalation and service-account-token mounting, uses the
runtime-default seccomp profile, and mounts a read-only root filesystem. Only
the profile volume is writable.

## Verification and publication gate

The local pip-audit check of all 18 locked server dependencies reported **zero
known vulnerabilities**. Package names/versions were checked against the advisory
service; private configuration was not submitted. Tests cover authentication
before parsing, request limits, cross-origin rejection, validation redaction,
unexposed configuration paths, persistence, offline cache behavior and Hue mocks.
Actionlint validates the workflow; zizmor's default offline audit reported no
findings. These tools are complementary and do not prove supply-chain safety.

The GitHub workflow:

1. Installs locked dependencies, lints and runs the full test suite.
2. Audits server dependencies; findings fail the job.
3. Builds the ARM64 image on a native ARM64 GitHub runner.
4. Scans OS and Python packages with Trivy; HIGH/CRITICAL findings fail, including
   issues without an available fix. A separate scan rejects secrets at every
   severity. Scanner errors also fail the job.
5. Checks image contents and starts it as a non-root, read-only container with
   capabilities dropped. Checks readiness and authenticated/unauthenticated APIs.
6. Only then logs into GHCR and publishes the exact scanned local image, without
   rebuilding it. Tags identify the full commit and, for release builds, the Git tag.

Actions are pinned by commit SHA, checkout does not persist credentials, PRs
cannot publish, and only the separate publish job receives `packages: write`. There are no
Hue credentials in CI. Repository code and workflow changes must still be reviewed:
any maintainer who can change a publishing workflow can change what it publishes.

## Remaining limits

Docker and kubectl were unavailable on the review machine. The final image's OS
scan, ARM64 startup and live k3s/Hue integration **have not been run locally**.
Successful CI is required before treating a particular image as cleared by the
publication gate. New vulnerability disclosures can invalidate an earlier scan.
Pinned bases must be updated and rebuilt to receive OS fixes.

The shared portal token grants full profile-editing and light-control access.
There are no per-user roles or login rate limits; use a randomly generated token,
not a human password, and keep the portal on the LAN. Anyone with cluster/node
administrative access can read its runtime secrets and volume. TLS terminates at
ingress; traffic inside the cluster is HTTP. No NetworkPolicy is installed because
the bridge address and network layout are installation-specific.

The HTTPS ingress requires a hostname and certificate trusted by the phone and
PC; it is not provisioned automatically. A private CA used by the PC sync client
can be supplied using `hue-sync --ca-file PATH_TO_CA_BUNDLE`. Do not disable verification to work
around a certificate mismatch. The app's `HUE_INSECURE` setting applies only to
the local Hue bridge and remains false by default.

References: [GitHub Actions security guidance](https://docs.github.com/en/actions/reference/security/secure-use),
[Trivy action](https://github.com/aquasecurity/trivy-action),
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## First CI run: base-image findings

[Run 36171247293](https://github.com/Griggum/hue-gaming/actions/runs/36171247293)
successfully built ARM64 and passed application tests, but Trivy blocked release
with 44 HIGH findings (zero CRITICAL) in Debian 13.7 packages, including
util-linux, ncurses, systemd, acl and perl. The report showed no fixed versions
for these entries. The image was not published; the secret scan and smoke test
were skipped after the failed vulnerability gate.

The Dockerfile now uses a digest-pinned Python 3.12 Alpine base in both stages,
removing the Debian package set rather than suppressing the findings. This keeps
the Python minor version unchanged. PR workflows now build, scan and smoke-test
the ARM64 container as well, so future base-image PRs cannot pass on Python unit
tests alone. The revised image still must pass the same strict scan before release.
