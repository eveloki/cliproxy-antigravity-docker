# Third-party components

This repository's original packaging code is MIT licensed. This does not relicense
its dependencies or Google's software, nor establish permission for any service use.

| Component | Source | Handling |
| --- | --- | --- |
| CLIProxyAPI | https://github.com/router-for-me/CLIProxyAPI | MIT; built from the commit pinned in Dockerfile; LICENSE copied into image |
| cliproxy-antigravity | https://github.com/adeebahmad01/cliproxy-antigravity | MIT; built from pinned commit plus the disclosed compat/ routing patch; LICENSE and notices copied into image |
| Google Antigravity CLI | https://github.com/google-antigravity/antigravity-cli/releases/tag/1.2.12 | Official Linux x64 binary bundled unmodified for the owner's personal deployment; exact archive SHA256 in upstream-versions.json |
| Debian and Go dependencies | Debian package metadata / upstream go.mod | Their respective licenses apply; image build emits an SBOM |

The runtime keeps upstream licenses under `/opt/cliproxy/licenses` and Debian
package notices under `/usr/share/doc`. The SBOM is an inventory, not a replacement
for license notices. Maintainers must review dependency distribution requirements
before publishing a stable release. This community project is not endorsed by Google
or either upstream project. Personal use does not grant third-party redistribution rights.
Google CLI remains subject to https://antigravity.google/terms and is not covered by
this repository's MIT license. Bundling does not guarantee compliance with
account/service terms and does not guarantee freedom from account restrictions.
