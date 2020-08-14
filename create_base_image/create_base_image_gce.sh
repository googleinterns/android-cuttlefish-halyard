#!/bin/bash

set -x
set -o errexit

sudo apt-get update

# Stuff we need to get build support
sudo apt install -y debhelper ubuntu-dev-tools equivs cloud-utils git bsdtar

repository_url=$1
repository_branch=$2
build_branch=$3
build_target=$4
build_id=$5

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
  cf_version=(*.dsc)
  cf_version=$(basename "${cf_version/*_/}" .dsc)
  cf_version="${cf_version//\./-}"
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

fetch_cf_package "${repository_url}" "${repository_branch}" 
get_cf_version

# Gets latest successful build_id from target branch in case no build_id is specified
if [[ -z "${build_id}" ]]; then
  build_id=`curl "https://www.googleapis.com/android/internal/build/v3/builds?branch=$build_branch&buildAttemptStatus=complete&buildType=submitted&maxResults=1&successful=true&target=$build_target" 2>/dev/null | \
  python2 -c "import sys, json; print json.load(sys.stdin)['builds'][0]['buildId']"`
fi

# Writes dest image and family values into file
name_values=("cf_version=${cf_version}" "FLAGS_build_id=${build_id}")
printf "%s\n" "${name_values[@]}" > image_name_values

# Install the cuttlefish build deps
for dsc in *.dsc; do
  yes | sudo mk-build-deps -i "${dsc}" -t apt-get
done

# Installing the build dependencies left some .deb files around. Remove them
# to keep them from landing on the image.
yes | rm -f *.deb

for dsc in *.dsc; do
  # Unpack the source and build it

  dpkg-source -x "${dsc}"
  dir="$(basename "${dsc}" .dsc)"
  dir="${dir/_/-}"
  pushd "${dir}/"
  debuild -uc -us
  popd
done

# Now gather all of the *.deb files to copy them into the image
debs=(*.deb)

tmp_debs=()
for i in "${debs[@]}"; do
  tmp_debs+=(/tmp/"$(basename "$i")")
done

# Fix partition table size
sudo growpart /dev/sdb 1
sudo e2fsck -f /dev/sdb1
sudo resize2fs /dev/sdb1

# Now install the packages on the disk
sudo mkdir /mnt/image
sudo mount /dev/sdb1 /mnt/image
cp "${debs[@]}" /mnt/image/tmp

# Fetches build artifacts 
sudo mkdir /mnt/image/usr/local/share/cuttlefish
sudo chmod -R 777 /mnt/image/usr/local/share/cuttlefish
pushd /mnt/image/usr/local/share/cuttlefish
fetch_build_artifacts "${build_target}" "${build_id}"
popd

sudo mount -t sysfs none /mnt/image/sys
sudo mount -t proc none /mnt/image/proc
sudo mount --bind /dev/ /mnt/image/dev
sudo mount --bind /dev/pts /mnt/image/dev/pts
sudo mount --bind /run /mnt/image/run
# resolv.conf is needed on Debian but not Ubuntu
sudo cp /etc/resolv.conf /mnt/image/etc/
sudo chroot /mnt/image /usr/bin/apt update
sudo chroot /mnt/image /usr/bin/apt install -y "${tmp_debs[@]}"
# install tools dependencies
sudo chroot /mnt/image /usr/bin/apt install -y python
sudo chroot /mnt/image /usr/bin/apt install -y openjdk-11-jre
sudo chroot /mnt/image /usr/bin/apt install -y unzip bzip2 lzop
sudo chroot /mnt/image /usr/bin/apt install -y aapt
sudo chroot /mnt/image /usr/bin/apt install -y screen # needed by tradefed

sudo chroot /mnt/image /usr/bin/find /home -ls


# Install GPU driver dependencies
sudo chroot /mnt/image /usr/bin/apt install -y gcc
sudo chroot /mnt/image /usr/bin/apt install -y linux-source
sudo chroot /mnt/image /usr/bin/apt install -y linux-headers-`uname -r`
sudo chroot /mnt/image /usr/bin/apt install -y make

# Download the latest GPU driver installer
gsutil cp \
  $(gsutil ls gs://nvidia-drivers-us-public/GRID/GRID*/*-Linux-x86_64-*.run \
    | sort \
    | tail -n 1) \
  /mnt/image/tmp/nvidia-driver-installer.run

# Make GPU driver installer executable
chmod +x /mnt/image/tmp/nvidia-driver-installer.run

# Install the latest GPU driver with default options and the dispatch libs
sudo chroot /mnt/image /tmp/nvidia-driver-installer.run \
  --silent \
  --install-libglvnd

# Cleanup after install
rm /mnt/image/tmp/nvidia-driver-installer.run

# Verify
query_nvidia() {
  sudo chroot /mnt/image nvidia-smi --format=csv,noheader --query-gpu="$@"
}

if [[ $(query_nvidia "count") != "1" ]]; then
  echo "Failed to detect GPU."
  exit 1
fi

if [[ $(query_nvidia "driver_version") == "" ]]; then
  echo "Failed to detect GPU driver."
  exit 1
fi

# Vulkan loader
sudo chroot /mnt/image /usr/bin/apt install -y libvulkan1

# Clean up the builder's version of resolv.conf
sudo rm /mnt/image/etc/resolv.conf

# Skip unmounting:
#  Sometimes systemd starts, making it hard to unmount
#  In any case we'll unmount cleanly when the instance shuts down

echo IMAGE_WAS_CREATED
