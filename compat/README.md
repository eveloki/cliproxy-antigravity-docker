# CPA v8 static executor routing compatibility

This distribution applies `plugin-model-router.patch` and adds
`distribution_router.go` to cliproxy-antigravity v0.1.3 during the image build.
The resulting plugin identifies itself as `0.1.3+cpa8-route1`. CPA is unchanged.
This is an explicit downstream compatibility patch, not an upstream release.

CPA v8 only takes its direct plugin executor path after a ModelRouter returns
`Handled: true, TargetKind: self`. The upstream plugin advertises a static
executor but no router, so an empty CPA auth pool yields `auth_not_found` before
the official CLI can run. This patch supplies the missing ABI capability and
`model.route` handler for **nonempty `agy/*` names only**. It leaves bare model
names and the native `antigravity/*` provider alone. Incoming client API-key
validation remains in CPA; Google authentication remains in the official CLI.
There are no synthetic provider credentials and no token extraction.

`git apply --check` must succeed before the build modifies upstream sources.
New upstream versions that invalidate the patch or already add the route will
fail the build/tests and require review; no silent patch skipping is allowed.
The upstream pins plus the patch/source SHA256 values are recorded inside
`/opt/cliproxy/upstream-versions.txt`.

Checks: Go tests exercise the real ABI dispatcher, namespace exclusions and
invalid JSON. The Docker test checks the full HTTP path with a mock CLI,
non-streaming and SSE responses, the exact selected model, and client API auth.
Passing these checks does not validate Google login, token refresh or real
model availability. Remove this compatibility layer after a tested upstream
release provides the same behavior.
