#!/bin/bash
 
target="$1"
build_id="$2"

FETCH_ARTIFACTS="$(mktemp)"
curl "https://www.googleapis.com/android/internal/build/v3/builds/$build_id/$target/attempts/latest/artifacts/fetch_cvd?alt=media" -o $FETCH_ARTIFACTS
chmod +x $FETCH_ARTIFACTS
exec $FETCH_ARTIFACTS
