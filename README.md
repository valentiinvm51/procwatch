# ProcWatch (cPanel/WHM Plugin)

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

🚀 Live preview: [https://afbora.github.io/procwatch/preview.html](https://afbora.github.io/procwatch/preview.html)

<img width="1440" height="1244" alt="preview" src="https://github.com/user-attachments/assets/9056b445-1a60-4e6f-befc-bcf336b0869e" />

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

- WHM AppConfig (registered via `register_appconfig`):
  - Source: `adapters/whm/appconfig/procwatch.conf`
  - cPanel stores a copy under `/var/cpanel/apps/`

- WHM CGI:
  - UI (Perl CGI that renders Template Toolkit wrapper): `/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/index.cgi`
  - Metrics JSON endpoint (bash): `/usr/local/cpanel/whostmgr/docroot/cgi/procwatch/metrics.cgi`

- WHM interface template (Template Toolkit):
  - `/usr/local/cpanel/whostmgr/docroot/templates/procwatch/index.tmpl`

- Icon:
  - `/usr/local/cpanel/whostmgr/docroot/addon_plugins/procwatch.png`

- Cache directory:
  - `/var/cache/procwatch/` (stores a short-lived JSON snapshot)

No services are started. No cron jobs are created.

---

## Install

### Quick install (recommended)

```bash
git clone https://github.com/afbora/procwatch.git \
  && cd procwatch \
  && sudo bash adapters/whm/install.sh
```

### Manual install (step-by-step)

```bash
git clone https://github.com/afbora/procwatch.git
cd procwatch

# Review installer + what will be installed
sed -n '1,200p' adapters/whm/install.sh
sed -n '1,120p' adapters/whm/appconfig/procwatch.conf

# Install
sudo bash adapters/whm/install.sh
```

After install:
- Log into **WHM**
- Find **ProcWatch** in the left menu
- Open it to see the dashboard.

## Uninstall

### Quick uninstall

```bash
cd /root/procwatch
sudo bash adapters/whm/uninstall.sh
```

### Manual uninstall (step-by-step)

```bash
cd /root/procwatch

# Review uninstaller
sed -n '1,200p' adapters/whm/uninstall.sh

# Uninstall
sudo bash adapters/whm/uninstall.sh
```

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

## Safety & resource usage

ProcWatch is designed to be safe to run on busy servers:

- **No daemon / no cron** in MVP: the collector runs only when you open the WHM page.
- **Short cache TTL** (default: 5s): prevents expensive collection on every refresh.
- **Hard timeouts**: `ps` / `df` collection is guarded by `timeout` (when available).
- **Low priority execution**: collection is run with `nice` (and `ionice` when available).
- **Process list hard cap**: `ps` is capped to a fixed number of rows to avoid pathological cases.
- **Fail-safe output**: on partial failures/timeouts, the dashboard still renders and shows a small warning indicator.

> If `timeout` is not available on your system, ProcWatch falls back to best-effort execution (still cached + low priority).


## Access control (ACL)

By default, ProcWatch is **root-only** in WHM.

This is enforced via the AppConfig setting:

```ini
acls=all
```

In WHM, `all` effectively means **root only**, because only the root user has *all* privileges.
Resellers and delegated WHM users will **not** see the plugin.

If you explicitly want resellers or delegated users to access ProcWatch, you may relax this setting:

```ini
acls=any
```

After changing the ACL, re-register the plugin:

```bash
/usr/local/cpanel/bin/register_appconfig adapters/whm/appconfig/procwatch.conf
```

> ⚠️ ProcWatch exposes server-wide process and resource information.  
> Making it visible to non-root users is **not recommended**.
