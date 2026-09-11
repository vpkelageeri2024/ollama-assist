#!/bin/bash
set -e

echo "🧞 Preparing to build WishOS Live USB..."

# 1. Install Debian live-build tools
echo "Installing live-build..."
sudo apt-get update
sudo apt-get install -y live-build debootstrap curl

# 2. Set up the build directory
BUILD_DIR="$HOME/wishos-build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Configuring the OS base..."
sudo lb clean
lb config -d bookworm --debian-installer live --archive-areas "main contrib non-free"

# 3. Add necessary system packages to the OS
mkdir -p config/package-lists
echo "curl git wget sudo ca-certificates dialog" > config/package-lists/wishos.list.chroot

# 4. Create the custom installer hook for the AI
mkdir -p config/hooks/normal
cat << 'HOOK' > config/hooks/normal/01-setup-ai.hook.chroot
#!/bin/sh
set -e

echo "Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

echo "Installing Terminal Wish..."
npm install -g terminal-wish
HOOK
chmod +x config/hooks/normal/01-setup-ai.hook.chroot

# 5. Force Terminal Wish to open the moment the OS boots up
mkdir -p config/includes.chroot/etc/skel
echo "terminal-wish" >> config/includes.chroot/etc/skel/.bashrc

echo "================================================="
echo "Configuration complete! Ready to compile the ISO."
echo "Note: The final build step takes 20-40 minutes and"
echo "requires downloading a full Linux filesystem."
echo "================================================="
echo ""
echo "To start the build, run: sudo lb build"
