# Termux guide for the VPS security toolkit

This repository is accessed through the user's second GitHub account (`zh-st1313`).
Use it locally on Android **Termux**, not as an installable GitHub-hosted service.

## Connectivity
Remote Desktop Commander currently reported **both registered devices offline** when this file was prepared. No commands have been executed on the user's phone and no software has been installed on the VPS.

## Recommended installation

In a genuine Termux session (non-root):

```sh
pkg install -y git
git clone -b security/vps-toolkit --single-branch https://github.com/zh-st1313/Entekhabreshte-test.git
cd Entekhabreshte-test/security/vps-toolkit
bash scripts/install-termux.sh                   # preview, no changes
bash scripts/install-termux.sh --apply           # install 3 Termux-compatible audit tools
```

Optional (significant storage/RAM requirement):

```sh
bash scripts/install-termux.sh --apply --with-nuclei
```

**Supported directly on Termux:** Nmap (some low-level scan modes need root), ssh-audit, testssl.sh, and optional Nuclei. No target or production address is hardcoded. Downloads are from official upstream repositories and Termux packages.

**NOT supported as fully functional native Termux services:** Fail2ban (needs system log and packet filtering integration), CrowdSec (needs supported Linux service/remediation integration), Wazuh agent/manager, and Lynis full Linux system audit. Metasploit and LinPEAS require a separately managed Linux testing environment for their relevant use cases. Trivy is not installed by this Termux script due to compatibility and large toolchain concerns. See main README for the full catalog of 11 tools.

## Verification

```sh
command -v nmap
command -v ssh-audit
test -f "$HOME/.local/share/vps-toolkit/testssl.sh/testssl.sh" && echo "testssl.sh present"
command -v nuclei || test -x "$HOME/go/bin/nuclei"
```

For **actual VPS hardening**, connect securely to the *authorized VPS* and use the Debian/Ubuntu host-specific installers only after a backup/snapshot and console-access check. Do not blindly run Linux system service install scripts inside Android or deploy them to the live production VPS.

## Safety

- Never paste your VPS password, token, or private SSH key into a public GitHub repository.
- This branch is separate from `main`; no application files or existing datasets were modified.
- Installing these tools does not mean the server has been penetration-tested or protected.
