# ProcWatch (cPanel/WHM Plugin) — MVP

ProcWatch is a lightweight, **process-aware** server snapshot page designed to run inside **WHM** (cPanel).
It shows, in a single screen:

- CPU usage (incl. iowait)
- Memory + swap
- Load average
- Disk usage
- Top accounts (aggregated by process owner; **PHP-FPM pool workers are attributed per-account**)
- Top processes (CPU/RAM/elapsed)
- Top PHP-FPM pools (pool-level view)

This repository is intentionally **simple**:
- No historical charts (MVP)
- No external databases
- No heavy dependencies

> **Scope:** WHM (root / reseller). Not intended for end-user cPanel accounts.

---

## Requirements

### Supported platforms
This plugin targets **cPanel-supported Linux distributions** (Linux only).  
It relies on standard Linux interfaces and tools:

- `/proc` (CPU/memory/load basics)
- `ps`
- `df`
- `awk`, `sed`, `grep`, `head`, `sort` (standard userland)

### Privileges
- Install/uninstall requires **root**.
- Runtime executes in WHM CGI context and expects access to process listing.

### Optional assumptions
- Account attribution is strongest when PHP runs via **per-account PHP-FPM pools** (common on cPanel).  
  If PHP is not using per-account pools, account attribution becomes "best-effort".

---

## What gets installed (files)

The installer copies files to:

- WHM AppConfig:
  - `/var/cpanel/apps/procwatch.conf`

- WHM CGI (plugin UI + JSON endpoint):
  - `/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/index.cgi`

- Cache directory:
  - `/var/cache/procwatch/` (stores a short-lived JSON snapshot)

No services are started. No cron jobs are created.

---

## Install

SSH as `root`, then:

```bash
git clone https://github.com/<your-org-or-user>/procwatch.git
cd procwatch
sudo bash adapters/whm/install.sh
```

After install:
- Log into **WHM**
- Look for **ProcWatch** in the left menu
- Open it to see the dashboard.

---

## Uninstall

SSH as `root`, then:

```bash
cd procwatch
sudo bash adapters/whm/uninstall.sh
```

---

## How it works

### Data collection
The CGI script produces a JSON snapshot on demand. To keep it fast, it writes a cached snapshot to:

- `/var/cache/procwatch/metrics.json`

Cache TTL is short (default 5 seconds). The UI refreshes every 5 seconds.

### Account & pool attribution
- Processes are grouped by Linux process owner (user).
- PHP-FPM pool workers are detected by scanning for commands like:
  - `php-fpm: pool <pool_name>`

The dashboard shows:
- **Top accounts** by CPU and memory (sum of process CPU% and RSS).
- **Top pools** by CPU and memory with worker count.

---

## Security notes

- This is a **WHM-only** page intended for administrators.
- The plugin does not accept user input for executing commands.
- Output is read-only JSON + HTML.

---

## License

MIT — see [LICENSE](LICENSE).
