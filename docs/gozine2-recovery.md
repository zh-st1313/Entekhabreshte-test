# Gozine2 public archive recovery

Temporary research tooling for recovering **publicly available** historical Gozine2 KonkurResult traces without logging into Norato or bypassing account/query limits.

The script checks:
- public Telegram channel archives and old report-card posts;
- historical Gozine2 URLs through the Internet Archive CDX index;
- legacy short links used by Gozine2;
- archived HTML forms, script references, and result-related links.

Outputs are written under \`artifacts/gozine2/\` and uploaded as a GitHub Actions artifact.

No authenticated Norato requests, account automation, or query-limit bypassing is performed.
