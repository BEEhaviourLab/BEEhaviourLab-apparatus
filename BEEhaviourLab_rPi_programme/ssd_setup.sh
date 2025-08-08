#!/bin/bash

set -e

# ---- USER CONFIG ----
USERNAME=$(whoami)
MOUNT_DIR="/home/$USERNAME/myssd"
UUID_FILE="/home/$USERNAME/ssd_uuid.txt"

echo "🔍 Scanning for ext4-formatted SSD..."
SSD_UUID=$(lsblk -o UUID,NAME,FSTYPE,SIZE,MOUNTPOINT,LABEL,MODEL | grep ext4 | awk '{print $1}' | head -n 1)

if [ -z "$SSD_UUID" ]; then
    echo "No ext4-formatted SSD detected. Make sure it's partitioned and formatted."
    exit 1
fi

echo "SSD UUID found: $SSD_UUID"
echo "$SSD_UUID" > "$UUID_FILE"
echo "UUID saved to $UUID_FILE"

echo "Creating mount directory at $MOUNT_DIR..."
sudo mkdir -p "$MOUNT_DIR"
sudo chown "$USERNAME":"$USERNAME" -R "$MOUNT_DIR"
sudo chmod a+rwx "$MOUNT_DIR"

echo "Adding mount entry to /etc/fstab..."
FSTAB_LINE="UUID=$SSD_UUID $MOUNT_DIR ext4 defaults,auto,users,rw,nofail 0 0"
if ! grep -q "$SSD_UUID" /etc/fstab; then
    echo "$FSTAB_LINE" | sudo tee -a /etc/fstab
else
    echo "UUID already present in /etc/fstab. Skipping."
fi

echo "Mounting SSD now..."
sudo mount -a

echo "Fixing ownership and permissions..."
sudo chown -R "$USERNAME":"$USERNAME" "$MOUNT_DIR"
sudo chmod -R 755 "$MOUNT_DIR"

echo "SSD mounted and set to auto-mount on boot."
