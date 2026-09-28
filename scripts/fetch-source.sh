#!/usr/bin/env bash
set -euo pipefail
repo=$1
revision=$2
destination=$3
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected a full upstream commit SHA.' >&2; exit 2; }
git init -q "$destination"
git -C "$destination" remote add origin "$repo"
git -C "$destination" fetch --depth 1 origin "$revision"
git -C "$destination" checkout --detach FETCH_HEAD
[[ "$(git -C "$destination" rev-parse HEAD)" == "$revision" ]]
