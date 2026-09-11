#!/bin/bash
set -e

echo "🧞 Preparing to build Wish OS (Linux + Android + AI Hybrid)..."

# 1. Install ISO builder tools
sudo apt-get update
sudo apt-get install -y live-build curl gnupg

# 2. Setup Build Environment
mkdir -p ~/wishos-build
cd ~/wishos-build
sudo lb clean || true
rm -rf .build config || true

# Configure the OS branding as "Wish OS"
lb config \
    --mode debian \
    --system live \
    --distribution bookworm \
    --archive-areas "main contrib non-free non-free-firmware" \
    --iso-volume "Wish OS" \
    --bootappend-live "boot=live components hostname=wishos username=wish user-fullname=Wish_OS locales=en_US.UTF-8"

# 3. Add Core Desktop Packages
mkdir -p config/package-lists
cat << 'LIST' > config/package-lists/wishos.list.chroot
task-gnome-desktop
curl
git
wget
sudo
ca-certificates
lxc
LIST

# 4. Create the Hook to install Waydroid and AI
mkdir -p config/hooks/normal
cat << 'HOOK' > config/hooks/normal/01-setup-hybrid.hook.chroot
#!/bin/sh
set -e

# Add Waydroid (Android Subsystem) Repository
curl -s https://repo.waydro.id | bash
apt-get install -y waydroid

# Add Node.js and AI tools
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs
curl -fsSL https://ollama.com/install.sh | sh
npm install -g terminal-wish

# Enable Waydroid background service on boot
systemctl enable waydroid-container
HOOK
chmod +x config/hooks/normal/01-setup-hybrid.hook.chroot

echo "================================================="
echo "Configuration complete! We are ready to compile Wish OS."
echo "Run this command to build the ISO (takes ~30 mins):"
echo "cd ~/wishos-build && sudo lb build"
echo "================================================="
