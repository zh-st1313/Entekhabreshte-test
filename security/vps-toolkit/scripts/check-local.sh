#!/usr/bin/env bash
# Read-only local binary inventory; no target systems contacted.
set -Eeuo pipefail
echo "Tool | status / location"
echo "----------------------"
for item in "nmap:nmap" "ssh-audit:ssh-audit" "lynis:lynis" "nuclei:nuclei" "trivy:trivy" "fail2ban:fail2ban-client" "crowdsec:cscli" "wazuh-agent:wazuh-agentd" "metasploit:msfconsole"; do
  name="${item%%:*}"; binary="${item#*:}"
  found="$(command -v "$binary" 2>/dev/null || true)"
  [[ -z "$found" && -x "$HOME/.local/bin/$binary" ]] && found="$HOME/.local/bin/$binary"
  [[ -z "$found" && -x "$HOME/go/bin/$binary" ]] && found="$HOME/go/bin/$binary"
  printf '%s | %s\n' "$name" "${found:-not found}"
done
if [[ -f "$HOME/.local/share/vps-toolkit/testssl.sh/testssl.sh" ]]; then
  echo "testssl.sh | $HOME/.local/share/vps-toolkit/testssl.sh/testssl.sh"
else
  echo "testssl.sh | not found"
fi
if [[ -f "$HOME/.local/share/vps-toolkit/lab/linpeas.sh" ]]; then
  echo "LinPEAS | downloaded (not executed)"
else
  echo "LinPEAS | not found"
fi
