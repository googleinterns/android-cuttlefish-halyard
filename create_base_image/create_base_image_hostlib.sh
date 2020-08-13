#!/bin/bash

# Common code to build a host image on GCE

source "../external/shflags/shflags"

# Build instance info
DEFINE_string build_instance \
  "${USER}-build" "Instance name to create for the build" "i"
DEFINE_string build_project "$(gcloud config get-value project)" \
  "Project to use for scratch"
DEFINE_string build_zone "$(gcloud config get-value compute/zone)" \
  "Zone to use for scratch resources"
DEFINE_string build_tags "" "Tags to add to the GCE instance"
IMAGE_DISK="${USER}-image-disk"

# Build artifacts info
DEFINE_string build_branch "aosp-master" \
  "Branch to extract build artifacts" "b"
DEFINE_string build_target "aosp_cf_x86_phone-userdebug" \
  "Target device to extract build artifacts"
DEFINE_string build_id "" \
  "Build id used to extract build artifacts"

# New image info
DEFINE_string dest_image "" \
  "Image to create" "o"
DEFINE_string dest_family "" \
  "Image family to add the image to" "f"
DEFINE_string dest_project "" \
  "Project to use for the new image" "p"
DEFINE_boolean respin false \
  "Whether to replace an image if its name is taken"

# Base image info
DEFINE_string source_image_family "debian-10" \
  "Image family to use as the base" "s"
DEFINE_string source_image_project "debian-cloud" \
  "Project holding the base image" "m"

# CF repo info
DEFINE_string repository_url \
  "https://github.com/google/android-cuttlefish.git" \
  "URL to the repository with host changes" "u"
DEFINE_string repository_branch master \
  "Branch to check out"



fatal_echo() {
  echo "$1"
  exit 1
}

# Sleeps while trying to connect to instance
wait_for_instance() {
  alive=""
  while [[ -z "${alive}" ]]; do
    sleep 5
    alive="$(gcloud compute ssh "$@" -- uptime || true)"
  done
}

# Gets debian packages from Cuttlefish repo
fetch_cf_package() {

  local url="$1"
  local branch="$2"
  local repository_dir="${url/*\//}"
  local debian_dir="$(basename "${repository_dir}" .git)"

  git clone "${url}" -b "${branch}"
  dpkg-source -b "${debian_dir}"
  rm -rf "${debian_dir}"

}

get_cf_version() {
  CF_VER=(*.dsc)
  CF_VER=$(basename "${CF_VER/*_/}" .dsc)
  CF_VER="${CF_VER//\./-}"
}

# Gets build artifacts from Android Build API
fetch_build_artifacts() {

  local target="$1"
  local build_id="$2"
  
  FETCH_ARTIFACTS="$(mktemp)"
  curl "https://www.googleapis.com/android/internal/build/v3/builds/$build_id/$target/attempts/latest/artifacts/fetch_cvd?alt=media" -o $FETCH_ARTIFACTS

  chmod +x $FETCH_ARTIFACTS
  eval $FETCH_ARTIFACTS

}


main() {
  set -o errexit
  set -x

  # SETUP AND SOURCE FILES EXTRACTION

  # Flags setup
  PZ=(--project=${FLAGS_build_project} --zone=${FLAGS_build_zone})
  if [[ -n "${FLAGS_build_tags}" ]]; then
    build_tags=("--tags=${FLAGS_build_tags}")
  else
    build_tags=()
  fi

  # Gets latest successful build_id from target branch in case no build_id is specified
  if [[ -z "${FLAGS_build_id}" ]]; then
    FLAGS_build_id=`curl "https://www.googleapis.com/android/internal/build/v3/builds?branch=$FLAGS_build_branch&buildAttemptStatus=complete&buildType=submitted&maxResults=1&successful=true&target=$FLAGS_build_target" 2>/dev/null | \
    python2 -c "import sys, json; print json.load(sys.stdin)['builds'][0]['buildId']"`
  fi

  # Fetches cuttlefish common packages and target build artifacts
  scratch_dir="$(mktemp -d)"
  pushd "${scratch_dir}"
    fetch_cf_package "${FLAGS_repository_url}" "${FLAGS_repository_branch}"
    get_cf_version
    mkdir cuttlefish
    pushd cuttlefish
      fetch_build_artifacts "${FLAGS_build_target}" "${FLAGS_build_id}"
    popd
  popd
  source_files=(
    "create_base_image_gce.sh"
    "${scratch_dir}"/*
  )

  # Sets image and family names in case none were specified
  FLAGS_build_target="${FLAGS_build_target//_/-}"
  if [[ -z "${FLAGS_dest_image}" ]]; then
    FLAGS_dest_image="halyard-${CF_VER}-${FLAGS_build_branch}-${FLAGS_build_target}-${FLAGS_build_id}"
  fi
  if [[ -z "${FLAGS_dest_family}" ]]; then
    FLAGS_dest_family="halyard-${FLAGS_build_branch}-${FLAGS_build_target}"
  fi

  if [[ -n "${FLAGS_dest_family}" ]]; then
    dest_family_flag=("--family=${FLAGS_dest_family}")
  else
    dest_family_flag=()
  fi

  # Deletes instances and disks with names that will be used for build
  delete_instances=("${FLAGS_build_instance}" "${FLAGS_dest_image}")
  gcloud compute instances delete -q \
    "${PZ[@]}" "${FLAGS_build_instance}" || echo Not running
  gcloud compute disks delete -q \
    "${PZ[@]}" "${IMAGE_DISK}" || echo No scratch disk

  # Checks for existing image with same name
  gcloud compute images describe \
    --project="${FLAGS_build_project}" "${FLAGS_dest_image}" && \
    if [ ${FLAGS_respin} -eq ${FLAGS_TRUE} ]; then
      gcloud compute images delete -q \
        --project="${FLAGS_build_project}" "${FLAGS_dest_image}"
    else
      fatal_echo "Image ${FLAGS_dest_image} already exists. (To replace run with flag --respin)"
    fi

  # BUILD INSTANCE CREATION

  gcloud compute disks create \
    "${PZ[@]}" \
    --image-family="${FLAGS_source_image_family}" \
    --image-project="${FLAGS_source_image_project}" \
    --size=30GB \
    "${IMAGE_DISK}"

  # Checks if gpu available 
  local gpu_type="nvidia-tesla-p100-vws"
  gcloud compute accelerator-types describe "${gpu_type}" "${PZ[@]}" || \
    fatal_echo "Please use a zone with ${gpu_type} GPUs available."

  gcloud compute instances create \
    "${PZ[@]}" \
    --machine-type=n1-standard-16 \
    --image-family="${FLAGS_source_image_family}" \
    --image-project="${FLAGS_source_image_project}" \
    --boot-disk-size=200GiB \
    --accelerator="type=${gpu_type},count=1" \
    --maintenance-policy=TERMINATE \
    "${build_tags[@]}" \
    "${FLAGS_build_instance}"

  # Wait until instance is booted
  wait_for_instance "${PZ[@]}" "${FLAGS_build_instance}"

  gcloud compute instances attach-disk \
      "${PZ[@]}" "${FLAGS_build_instance}" --disk="${IMAGE_DISK}"

  gcloud compute scp "${PZ[@]}" -- -r \
    "${source_files[@]}" \
    "${FLAGS_build_instance}:"


  # IMAGE CREATION

  gcloud compute ssh "${PZ[@]}" "${FLAGS_build_instance}" -- \
    ./create_base_image_gce.sh

  gcloud compute instances delete -q \
    "${PZ[@]}" "${FLAGS_build_instance}"

  gcloud compute images create \
    --project="${FLAGS_build_project}" \
    --source-disk="${IMAGE_DISK}" \
    --source-disk-zone="${FLAGS_build_zone}" \
    --licenses=https://www.googleapis.com/compute/v1/projects/vm-options/global/licenses/enable-vmx \
    "${dest_family_flag[@]}" \
    "${FLAGS_dest_image}"

  gcloud compute disks delete -q \
    "${PZ[@]}" "${IMAGE_DISK}"

  if [[ -n "${FLAGS_dest_project}" && "${FLAGS_dest_project}" != "${FLAGS_build_project}" ]]; then
    gcloud compute images create \
      --project="${FLAGS_dest_project}" \
      --source-image="${FLAGS_dest_image}" \
      --source-image-project="${FLAGS_build_project}" \
      "${dest_family_flag[@]}" \
      "${FLAGS_dest_image}"
  fi

}
