#!/usr/bin/env bash
# Install the OpenBao release pinned by the openbao role defaults, checksum-verified,
# unpacked without installing the service, and put its bin directory on the job PATH.
# Needs GH_TOKEN, RUNNER_TEMP and GITHUB_PATH (set by Actions); run from the repository root.
set -euo pipefail

version=$(sed -n 's/^openbao_version: "\(.*\)"/\1/p' roles/openbao/defaults/main/00-install-and-node.yml)
[ -n "$version" ] || { echo "openbao_version not found in the role defaults" >&2; exit 1; }
deb="openbao_${version}_linux_amd64.deb"

cd "$RUNNER_TEMP"
gh release download "v$version" --repo openbao/openbao --pattern "$deb" --pattern checksums.txt
awk -v f="$deb" '$2 == f' checksums.txt | sha256sum --check --strict -
dpkg-deb --extract "$deb" openbao
echo "$RUNNER_TEMP/openbao/usr/bin" >> "$GITHUB_PATH"
