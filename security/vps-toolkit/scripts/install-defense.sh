#!/usr/bin/env bash
# Network protections are opt-in and must not be enabled blindly on production.
set -Eeuo pipefail
if [[ "${1:-}" != "--apply" ]]; then
  cat <<'EOF'
PREVIEW ONLY: defense profile
  - Fail2ban (via Ubuntu/Debian package manager)
  - CrowdSec detection engine (official package repository; requires review)
  - Wazuh agent: documented ONLY; requires manager and enrollment credentials
No firewall rules, ban policies, or Wazuh manager are configured automatically.
Usage: bash scripts/install-defense.sh --apply   (prefer a lab VM)
EOF
  exit 0
fi
if [[ "${I_HAVE_CONSOLE_ACCESS:-}" != "yes" ]]; then
  echo "Set I_HAVE_CONSOLE_ACCESS=yes only after confirming VPS out-of-band console access." >&2
  exit 1
fi
if [[ "$(id -u)" -eq 0 ]] || ! command -v sudo >/dev/null || ! command -v apt-get >/dev/null; then
  echo "Run as a non-root user with sudo on Debian/Ubuntu." >&2; exit 1
fi
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban curl ca-certificates
echo "Fail2ban package installed. Review jail and SSH access before enabling policies."
REPO_INSTALLER="${HOME}/crowdsec-install-repository.sh"
curl -fsSL https://install.crowdsec.net -o "$REPO_INSTALLER"
echo "CrowdSec repository installer downloaded to $REPO_INSTALLER"
echo "Review it; then follow https://docs.crowdsec.net/u/getting_started/installation/linux/"
echo "Wazuh is NOT auto-installed or enrolled: https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html"
echo "No firewall rule, CrowdSec bouncer, or remote manager endpoint changed."
