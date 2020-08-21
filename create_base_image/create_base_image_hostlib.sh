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

# Sets image and family names in case none were specified
update_dest_names() {

  # Reads cf_version
  name_values="$(mktemp)"
  gcloud compute scp "${PZ[@]}" -- \
    "${FLAGS_build_instance}:~/image_name_values" "${name_values}"
  while read -r line; do declare "$line"; done < "${name_values}"

  FLAGS_build_id="${build_id}"
  FLAGS_build_target="${FLAGS_build_target//_/-}"

}


main() {
  set -o errexit
  set -x

  # SETUP

  # Flags setup
  PZ=(--project=${FLAGS_build_project} --zone=${FLAGS_build_zone})
  if [[ -n "${FLAGS_build_tags}" ]]; then
    build_tags=("--tags=${FLAGS_build_tags}")
  else
    build_tags=()
  fi

  source_files=("create_base_image_gce.sh")

  # Deletes instances and disks with names that will be used for build
  gcloud compute instances delete -q \
    "${PZ[@]}" "${FLAGS_build_instance}" || echo Not running
  gcloud compute disks delete -q \
    "${PZ[@]}" "${IMAGE_DISK}" || echo No scratch disk


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

  # Checks for existing image with same name
  gcloud compute images describe \
    --project="${FLAGS_build_project}" "${FLAGS_dest_image}" && \
    if [ ${FLAGS_respin} -eq ${FLAGS_TRUE} ]; then
      gcloud compute images delete -q \
        --project="${FLAGS_build_project}" "${FLAGS_dest_image}"
    else
      fatal_echo "Image ${FLAGS_dest_image} already exists. (To replace run with flag --respin)"
    fi

  gcloud compute ssh "${PZ[@]}" "${FLAGS_build_instance}" -- \
    ./create_base_image_gce.sh \
      "${FLAGS_repository_url}" "${FLAGS_repository_branch}" \
      "${FLAGS_build_branch}" "${FLAGS_build_target}" "${FLAGS_build_id}"

  update_dest_names

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
