#!/bin/bash

# Creates a base image suitable for booting cuttlefish on GCE

source "create_base_image_hostlib.sh"

FLAGS "$@" || exit 1
main "${FLAGS_ARGV[@]}"
