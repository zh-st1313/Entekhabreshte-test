# VPS Security Toolkit (isolated from app code)

**Repository:** zh-st1313/Entekhabreshte-test  
**Branch:** security/vps-toolkit  
**Purpose:** Authorized, defensive audit of Linux VPS infrastructure.

> GitHub repositories are source storage, not a persistent VPS. Committing these files **does not install any software on the production server**. The optional install scripts must be executed on an authorized Ubuntu/Debian machine, preferably a disposable lab VM. No target IP, credential, API token, or production hostname is embedded in this repository.

## Included tools (11)

| Tool | Upstream | Mode | What it does |
|---|---|---|---|
| Nmap | https://github.com/nmap/nmap | audit | Discover exposed ports (use only with authorization) |
| ssh-audit | https://github.com/jtesta/ssh-audit | audit | Audit SSH configuration |
| Lynis | https://github.com/CISOfy/lynis | audit | Linux host security assessment |
| Nuclei | https://github.com/projectdiscovery/nuclei | audit | Template-based vulnerability checking |
| testssl.sh | https://github.com/testssl/testssl.sh | audit | TLS/HTTPS configuration |
| Trivy | https://github.com/aquasecurity/trivy | audit | Package/container vulnerability analysis |
| Fail2ban | https://github.com/fail2ban/fail2ban | defense | Rate-limit hostile authentication attempts |
| CrowdSec | https://github.com/crowdsecurity/crowdsec | defense | Detect abuse from logs; requires separate remediation component |
| Wazuh | https://github.com/wazuh/wazuh | defense | Endpoint agent + separate monitoring manager |
| Metasploit Framework | https://github.com/rapid7/metasploit-framework | isolated lab | Security validation in a disposable test environment |
| PEASS-ng / LinPEAS | https://github.com/peass-ng/PEASS-ng | isolated lab | Local privilege configuration assessment (requires authorized shell) |

## What is implemented

- `scripts/install-audit.sh`: opt-in installation of six audit tools on Debian/Ubuntu. Defaults to a preview, requires `--apply` to actually install.
- `scripts/install-defense.sh`: optionally installs Fail2ban and CrowdSec with explicit confirmation. Wazuh is documented, not auto-enrolled or exposed.
- `scripts/install-lab.sh`: prepares LinPEAS and the upstream Metasploit installer on a separate lab host, **without running exploits or executing an unreviewed installer**.
- `scripts/check-local.sh`: read-only detection of installed tools.
- CI: syntax checks; no scan of the production server or deployment of services.

## Usage (on a disposable Ubuntu/Debian VM)

```bash
cd security/vps-toolkit
bash scripts/check-local.sh
bash scripts/install-audit.sh             # preview only
bash scripts/install-audit.sh --apply     # installs on THIS machine, not on GitHub
bash scripts/install-defense.sh           # preview only
bash scripts/install-lab.sh               # preview only
```

Installers are intentionally modular and may require extra packages, platform support, version updates, or vendor-specific configuration. Validate on a snapshot before using on a live VPS.

## Important production warnings

1. Never run an unfamiliar script on a production host without inspecting it.
2. Back up the VPS, verify out-of-band console access, and keep an existing SSH session open before changing SSH or network protection.
3. CrowdSec requires a remediation component to actually block traffic; its engine alone does not provide blocking.
4. Wazuh requires a manager, agent enrollment, connectivity planning, and credentials. See https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html .
5. Install Metasploit only on a segregated lab machine; no exploit or destructive payload is included.
6. Never commit passwords, private SSH keys, production IP inventories, test results containing user data, or vulnerability details to this **public** repository.
