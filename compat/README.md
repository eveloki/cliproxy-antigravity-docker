# Distribution safeguards for upstream plugin v0.3.1

The candidate builds upstream commit `f2b4ac2c5fd5df7b9fe11f32b711715e3d39c60a`
with `plugin-distribution.patch` and `distribution_*.go`, identifying as
`0.3.1+dist1`. CPA source is not patched. `git apply --check`, upstream Go tests,
distribution Go tests and the upstream ABI smoke must pass before building the image.
No failed patch is silently skipped. Source commits and patch/helper SHA256 values
are recorded inside `/opt/cliproxy/upstream-versions.txt`.

## Retired v0.1.3 compatibility layer

The v0.1.3 ModelRouter/SSE patch is no longer applied. Upstream v0.2.0+ implements
ModelRouter, and CPA v8.0.75 handles upstream SSE framing. See the
[maintainer's reply](https://github.com/adeebahmad01/cliproxy-antigravity/issues/5#issuecomment-6903517407).
Applying the old patch to the new plugin caused the recent automated build failures.
The retired files remain available in git history.

## Remaining safeguards

- Keep published models and routing in the explicit `agy/*` namespace. Upstream's
  bare model IDs and `antigravity/*` aliases are excluded at the ABI boundary,
  preserving existing native CPA routing. Configured `agy` provider auth records
  retain upstream scheduling. Upstream may write token-free scheduling/quota metadata.
- Official CLI >=1.4.11 adds `finished_reason` for incomplete turns. A nonempty
  reason must not become a successful OpenAI completion. Reject timeout with 504,
  interruption/error/unknown reasons with 502. Streaming errors use upstream
  structured stream-close handling and never emit a successful finish chunk.
  Already streamed partial text cannot be retracted. Both wrapped and legacy flat
  terminal events are checked; normal results with no reason remain compatible.

Keep using image upgrades for this bundled plugin. A store binary can replace it
from a second path with the same plugin ID and remove these safeguards. The
managed checksum marker does not pin the active plugin. Older v0.1.3 store copies
also still have the historical routing defect. Do not infer that modern upstream
versions lack routing simply because the store restriction remains.

Local tests use mock inference. The real CLI binary is checked for version and
required arguments without login. Docker/old-volume checks remain release gates;
Google authentication and live model inference require deployment acceptance.
