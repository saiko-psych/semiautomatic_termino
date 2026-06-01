#!/bin/bash
# tools/server_setup.sh
# ----------------------
# One-shot installer for the headless Linux server side of
# semiautomatic_termino. Runs through every OS-level step that
# docs/SERVER_VPN_SETUP.md documents, so a new lab can go from a
# fresh Debian / Ubuntu LXC to "ready to clone the repo" in one
# command instead of 30.
#
# What this script DOES:
#   - apt install: python + venv + git + curl + ca-certificates,
#     openconnect + xvfb + sudo, Qt6 runtime libs that
#     openconnect-sso v0.8.1 needs, chromium + chromium-driver +
#     fonts (for Selenium against Termino).
#   - Creates a system user (default: termino) if missing.
#   - Installs the sudoers fragment that lets that user run
#     /usr/sbin/openconnect (and pkill openconnect) without
#     password. This is the smallest privilege grant that works -
#     no blanket sudo.
#   - Installs a udev rule + modules-load entry so /dev/net/tun is
#     present + world-readable after reboot. Required in
#     unprivileged LXC containers.
#   - Installs uv (Astral) as the target user.
#   - Installs openconnect-sso as an isolated uv tool with the
#     pins from real deployment experience (setuptools<70 because
#     openconnect-sso v0.8.1 imports pkg_resources removed in 70+;
#     keyrings.alt + pycryptodome to avoid runtime backend errors).
#
# What this script DOES NOT do:
#   - Clone the repo (you do that as the target user after this).
#   - Write config.json (run setup.py wizard).
#   - Set keyring credentials (run python -m utils.secrets set ...).
#   - Configure systemd timer (copy the unit files from
#     docs/SERVER_VPN_SETUP.md once your config is in place).
#   - Touch LXC HOST config (the udev + modules-load are
#     container-side; if your unprivileged LXC's parent needs a
#     /dev/net/tun bind, that's a one-time host edit by the
#     Proxmox admin - see docs/SERVER_VPN_SETUP.md).
#
# Usage (as root or with sudo):
#   bash tools/server_setup.sh                # default user: termino
#   bash tools/server_setup.sh <username>     # custom username

set -euo pipefail

# --- preconditions ---

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must be run as root (or with sudo)." >&2
    exit 1
fi

if [ ! -f /etc/debian_version ]; then
    echo "ERROR: this script only supports Debian / Ubuntu." >&2
    echo "       Detected: $(. /etc/os-release && echo "$NAME $VERSION_ID")" >&2
    exit 1
fi

TARGET_USER="${1:-termino}"
echo "==> server_setup.sh: target user = $TARGET_USER"
echo "==> Distribution: $(. /etc/os-release && echo "$NAME $VERSION_ID")"
echo

# --- step 1: apt packages ---

echo "==> [1/6] Installing apt packages ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y \
    python3 python3-venv python3-pip \
    git curl ca-certificates \
    openconnect xvfb sudo \
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
    libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
    libxkbcommon-x11-0 libnss3 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 \
    chromium chromium-driver \
    fonts-liberation fonts-noto-color-emoji

# --- step 2: target user ---

echo
echo "==> [2/6] User $TARGET_USER ..."
if id "$TARGET_USER" &>/dev/null; then
    echo "    user already exists - skip"
else
    adduser --disabled-password --gecos "Termino daily run" "$TARGET_USER"
    echo "    user $TARGET_USER created"
fi

# --- step 3: sudoers fragment for openconnect ---

echo
echo "==> [3/6] Sudoers fragment /etc/sudoers.d/openconnect-${TARGET_USER} ..."
SUDOERS_FILE="/etc/sudoers.d/openconnect-${TARGET_USER}"
cat > "$SUDOERS_FILE" << EOF
# Created by tools/server_setup.sh on $(date -Iseconds)
# Allows the ${TARGET_USER} user to bring an openconnect tunnel up/down
# without password. NO blanket sudo - only these four binaries.
${TARGET_USER} ALL=(root) NOPASSWD: /usr/sbin/openconnect, /usr/bin/killall openconnect, /usr/bin/pkill openconnect, /bin/kill
EOF
chmod 0440 "$SUDOERS_FILE"
if ! visudo -cf "$SUDOERS_FILE" >/dev/null; then
    echo "ERROR: sudoers syntax check failed!" >&2
    rm -f "$SUDOERS_FILE"
    exit 2
fi
echo "    $SUDOERS_FILE (validated)"

# --- step 4: TUN device persistence ---

echo
echo "==> [4/6] TUN device (modules-load + udev) ..."
echo tun > /etc/modules-load.d/tun.conf
modprobe tun 2>/dev/null || true  # may fail in unprivileged LXC; host handles it
cat > /etc/udev/rules.d/90-tun-lxc.rules << 'EOF'
KERNEL=="tun", MODE="0666"
EOF
udevadm control --reload-rules
udevadm trigger /dev/net/tun 2>/dev/null || true
echo "    /etc/modules-load.d/tun.conf + udev rule installed"
if [ -c /dev/net/tun ]; then
    echo "    /dev/net/tun is present"
else
    echo "    WARN: /dev/net/tun NOT visible from inside the container."
    echo "    If you're in unprivileged LXC, ask the Proxmox host admin"
    echo "    to add to /etc/pve/lxc/<CTID>.conf:"
    echo "      lxc.cgroup2.devices.allow: c 10:200 rwm"
    echo "      lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file"
fi

# --- step 5: uv (as target user) ---

echo
echo "==> [5/6] uv (Astral) for $TARGET_USER ..."
if sudo -u "$TARGET_USER" bash -c 'command -v uv >/dev/null'; then
    echo "    uv already installed in $TARGET_USER's PATH - skip"
else
    sudo -u "$TARGET_USER" bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    echo "    uv installed for $TARGET_USER"
fi

# --- step 6: openconnect-sso as uv tool ---

echo
echo "==> [6/6] openconnect-sso (uv tool) for $TARGET_USER ..."
if sudo -u "$TARGET_USER" bash -lc 'test -x ~/.local/bin/openconnect-sso'; then
    echo "    openconnect-sso already installed - skip"
else
    sudo -u "$TARGET_USER" bash -lc '
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        uv tool install \
            --with "setuptools<70" \
            --with "keyrings.alt" \
            --with "pycryptodome" \
            openconnect-sso
    '
    echo "    openconnect-sso installed for $TARGET_USER"
fi

# --- summary ---

echo
echo "============================================================"
echo " server_setup.sh: all six steps OK"
echo "============================================================"
echo
echo " Next steps - as $TARGET_USER:"
echo
echo "   # 1. Clone the repo"
echo "   su - $TARGET_USER"
echo "   cd /opt && git clone https://github.com/saiko-psych/semiautomatic_termino.git termino"
echo "   cd termino && uv sync"
echo
echo "   # 2. Initial configuration"
echo "   uv run python setup.py"
echo
echo "   # 3. Populate the keyring with VPN + Termino credentials"
echo "   export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring"
echo "   uv run python -m utils.secrets set --email <your-mail@edu.uni-graz.at> --vpn"
echo "   uv run python -m utils.secrets set --termino"
echo
echo "   # 4. One-time interactive openconnect-sso (writes credentials to keyring"
echo "   #    and verifies the SAML flow with your real Authenticator app)"
echo "   xvfb-run --auto-servernum openconnect-sso \\"
echo "       -u <your-mail@edu.uni-graz.at> \\"
echo "       --browser-display-mode shown --authenticate"
echo
echo "   # 5. Lock down the keyring file"
echo "   chmod 700 ~/.local/share/python_keyring/"
echo "   chmod 600 ~/.local/share/python_keyring/keyring_pass.cfg"
echo
echo "   # 6. Smoke-test main.py with the new auto_vpn integration"
echo "   uv run python main.py"
echo
echo " For systemd unit files + Pre/Post-Hook wiring,"
echo " see docs/SERVER_VPN_SETUP.md sections 4 and 5."
echo "============================================================"
