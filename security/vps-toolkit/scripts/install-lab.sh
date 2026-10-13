#!/usr/bin/env bash
# Lab-only acquisition of upstream tools, without automatic execution.
set -Eeuo pipefail
if [[ "${1:-}" != "--apply" ]]; then
  cat <<'EOF'
PREVIEW ONLY: isolated lab
 - Download LinPEAS from PEASS-ng official release without executing it
 - Download the official Rapid7 Metasploit installer without executing it
No active exploitation, privilege escalation, or target scanning.
Usage: I_AM_IN_ISOLATED_LAB=yes bash scripts/install-lab.sh --apply
EOF
  exit 0
fi
if [[ "${I_AM_IN_ISOLATED_LAB:-}" != "yes" ]]; then
  echo "Refusing: set I_AM_IN_ISOLATED_LAB=yes on a disposable lab VM only." >&2; exit 1
fi
for cmd in curl sha256sum; do command -v "$cmd" >/dev/null || { echo "Missing: $cmd" >&2; exit 1; }; done
LAB_DIR="${HOME}/.local/share/vps-toolkit/lab"
mkdir -p "$LAB_DIR"
curl -fL https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -o "$LAB_DIR/linpeas.sh"
curl -fL https://raw.githubusercontent.com/rapid7/metasploit-framework/master/msfinstall -o "$LAB_DIR/msfinstall"
chmod 600 "$LAB_DIR/linpeas.sh" "$LAB_DIR/msfinstall"
( cd "$LAB_DIR" && sha256sum linpeas.sh msfinstall > SHA256SUMS.local )
echo "Downloaded to $LAB_DIR, no script executed and no Metasploit application installed."
echo "For Metasploit installation follow https://docs.rapid7.com/metasploit/installing-the-metasploit-framework/"
