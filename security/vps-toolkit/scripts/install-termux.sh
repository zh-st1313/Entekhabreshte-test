#!/usr/bin/env bash
# Termux-native audit setup. No scans; nothing touches the remote VPS.
set -Eeuo pipefail
MODE="${1:-}"
WITH_NUCLEI="${2:-}"
if [[ "$MODE" != "--apply" ]]; then
  cat <<'EOF'
TERMUX INSTALL PREVIEW
  Native: Nmap (pkg), ssh-audit (Python), testssl.sh (git + bash)
  Optional: Nuclei (Go build; large download/compilation)
  Not native: Fail2ban, CrowdSec, Wazuh, Trivy, Lynis system audit,
              Metasploit, LinPEAS Linux elevation checks.
The latter require an appropriate Linux host/lab, not Android Termux.
Commands:
  bash scripts/install-termux.sh --apply
  bash scripts/install-termux.sh --apply --with-nuclei
No VPS is contacted, scanned or modified by this script.
EOF
  exit 0
fi
if ! command -v pkg >/dev/null 2>&1 || [[ -z "${PREFIX:-}" ]]; then
  echo "Requires the official Termux environment with pkg." >&2
  exit 1
fi
if [[ "$(id -u)" -eq 0 ]]; then
  echo "Do not run this as root; use the normal Termux user." >&2
  exit 1
fi
echo "Installing native Termux packages..."
pkg update -y
pkg install -y git curl python nmap openssl ca-certificates
echo "Installing ssh-audit from Python packages..."
if ! python -m pip install --no-input ssh-audit; then
  echo "WARNING: ssh-audit pip install failed; see error above." >&2
fi
TOOLS_DIR="$HOME/.local/share/vps-toolkit"
mkdir -p "$TOOLS_DIR"
if [[ ! -d "$TOOLS_DIR/testssl.sh/.git" ]]; then
  git clone --depth 1 https://github.com/testssl/testssl.sh.git "$TOOLS_DIR/testssl.sh"
fi
if [[ "$WITH_NUCLEI" == "--with-nuclei" ]]; then
  echo "Compiling Nuclei; Go build may exceed phone RAM/storage."
  pkg install -y golang
  if ! GOTOOLCHAIN=auto go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest; then
    echo "WARNING: Nuclei installation failed; see compiler output." >&2
  fi
fi
echo "Installation attempts complete; checking binaries:"
command -v nmap || true
command -v ssh-audit || true
test -f "$TOOLS_DIR/testssl.sh/testssl.sh" && echo "$TOOLS_DIR/testssl.sh/testssl.sh"
command -v nuclei || test ! -x "$HOME/go/bin/nuclei" || echo "$HOME/go/bin/nuclei"
echo "No live scan or server modification performed."
