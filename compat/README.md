# Distribution safeguards for upstream plugin v0.4.0

The candidate uses upstream commit `9054559e99e5a6fd8f834c90480977256816ddd1`
and identifies the custom plugin as `0.4.0+dist1`. CPA source remains unmodified.

## Syntax-based preparation

`prepare-plugin.go` parses upstream `agy.go` and `plugin.go` with Go's standard AST.
It identifies the result types, success checks, legacy flat terminal result,
model registration/static-model dispatch and routing dispatch by their syntax.
It adds the finished-reason guards and namespace wrappers and checks the source
plugin version against the pinned build argument before stamping `+dist1`.
Comments, blank lines and unrelated account/session code do not form part of a
line-based patch context. Both output files are parsed, validated and formatted
in memory before any source file is written.

Every required target must match exactly once. Missing, duplicated or already
changed contracts fail the build for review; no unknown structure is silently
skipped. `prepare-plugin_test.go` covers layout/session changes and failure without
partial source writes. Go tests, upstream ABI smoke and HTTP integration tests
remain required. Source commits and transformation/helper SHA256 values are
recorded in `/opt/cliproxy/upstream-versions.txt`.

The old v0.3.x unified patch failed on the account-aware changes in v0.4.0.
The retired patch and Python version stamper remain available in git history.

## Preserved safeguards

- Publish and route only `agy/*`; upstream's bare names and `antigravity/*` aliases
  remain excluded at the ABI boundary. Native `agy` credential scheduling and
  upstream account-bound conversation handling remain intact.
- Reject nonempty CLI `finished_reason`: timeout returns 504; interruption,
  errors and unknown early finishes return 502. Wrapped and legacy flat terminal
  results are checked, even for `status=SUCCESS` with exit code 0. Streaming
  failures never emit a successful finish chunk; text already streamed cannot be retracted.
- Preserve upstream v0.4.0's protocol-dependent SSE handling. Do not reinstate
  the retired v0.1.3 routing/SSE patch or change stream framing in this layer.

Store installation can still hot-replace the same plugin ID from another path,
removing these safeguards. Keep using tested image upgrades for this plugin;
the seeding checksum does not pin the active library.

Plugin v0.4.0 binds managed-account conversation IDs to the originating account.
Old raw IDs cannot resume those sessions; omit them and replay history or a summary.
See [upstream release notes](https://github.com/adeebahmad01/cliproxy-antigravity/releases/tag/v0.4.0).
No Google credentials or real inference are exercised in local/CI mocks.
