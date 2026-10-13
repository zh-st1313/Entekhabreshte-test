#!/usr/bin/env bash
# Opt-in six-tool security audit environment for Ubuntu/Debian. No scanning.
set -Eeuo pipefail
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "${1:-}" != "--apply" ]]; then
  cat <<'EOF'
PREVIEW ONLY. This installer would:
 - apt install nmap, lynis, git, python3-pip, pipx, golang-go, curl, ca-certificates
 - install ssh-audit via pipx
 - install Nuclei from its official Go module
 - clone the official testssl.sh repository into ~/.local/share/vps-toolkit
 - install Trivy using its official project installer
It does not scan, probe, or modify any remote system.
Usage: bash scripts/install-audit.sh --apply  (run on an authorized VM)
EOF
  exit 0
fi
if [[ "$(id -u)" -eq 0 ]]; then echo "Run as a normal user with sudo, not root." >&2; exit 1; fi
if ! command -v apt-get >/dev/null || ! command -v sudo >/dev/null; then
  echo "Ubuntu/Debian with sudo is required." >&2; exit 1
fi
echo "Installing six audit tools on THIS machine."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nmap lynis git curl ca-certificates python3 python3-pip pipx golang-go openssl
if ! command -v ssh-audit >/dev/null && [[ ! -x "$HOME/.local/bin/ssh-audit" ]]; then
  pipx install ssh-audit
fi
if ! command -v nuclei >/dev/null && [[ ! -x "$HOME/go/bin/nuclei" ]]; then
  GOTOOLCHAIN=auto go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
fi
mkdir -p "$HOME/.local/share/vps-toolkit"
if [[ ! -d "$HOME/.local/share/vps-toolkit/testssl.sh/.git" ]]; then
  git clone --depth 1 https://github.com/testssl/testssl.sh.git "$HOME/.local/share/vps-toolkit/testssl.sh"
fi
# Trivy upstream installer: downloaded for inspection before any execution.
TRIVY_INSTALL="$HOME/.local/share/vps-toolkit/install-trivy-upstream.sh"
curl -fsSL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh -o "$TRIVY_INSTALL"
echo "Trivy installer downloaded, NOT run: $TRIVY_INSTALL"
echo "Review it, then run: sh '$TRIVY_INSTALL' -b '$HOME/.local/bin'"
echo "Audit setup completed. Some components require PATH updates; no scans were executed."
bash "$BASE_DIR/scripts/check-local.sh"
