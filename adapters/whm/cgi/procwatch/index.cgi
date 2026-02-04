#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="/var/cache/procwatch"
CACHE_FILE="${CACHE_DIR}/metrics.json"
CACHE_TTL_SECONDS=5

http_header_json(){ printf "Content-Type: application/json\r\n\r\n"; }
http_header_html(){ printf "Content-Type: text/html; charset=utf-8\r\n\r\n"; }

query_param() {
  local key="$1"
  local qs="${QUERY_STRING:-}"
  local IFS='&'
  for pair in $qs; do
    local k="${pair%%=*}"
    local v="${pair#*=}"
    if [[ "$k" == "$key" ]]; then
      printf "%s" "$v"
      return 0
    fi
  done
  return 1
}

json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/ }"
  s="${s//$'\r'/ }"
  s="${s//$'\t'/ }"
  printf "%s" "$s"
}

file_mtime(){ stat -c %Y "$1" 2>/dev/null || echo 0; }
now_epoch(){ date +%s; }

ensure_cache_dir(){
  mkdir -p "${CACHE_DIR}" 2>/dev/null || true
  chmod 0755 "${CACHE_DIR}" 2>/dev/null || true
}

collect_cpu() {
  local a b
  a="$(awk '/^cpu /{print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)"
  sleep 0.2
  b="$(awk '/^cpu /{print $2,$3,$4,$5,$6,$7,$8,$9}' /proc/stat)"
  read -r au an as ai aw aq ar at <<<"$a"
  read -r bu bn bs bi bw bq br bt <<<"$b"

  local userd=$(( (bu+bn) - (au+an) ))
  local sysd=$(( (bs+br+bt) - (as+ar+at) ))
  local idled=$(( bi - ai ))
  local iowd=$(( bw - aw ))
  local totald=$(( (bu+bn+bs+bi+bw+bq+br+bt) - (au+an+as+ai+aw+aq+ar+at) ))
  if [[ "${totald}" -le 0 ]]; then totald=1; fi

  local pct=$(( ( (totald - idled) * 1000 ) / totald ))
  local userp=$(( ( userd * 1000 ) / totald ))
  local sysp=$(( ( sysd * 1000 ) / totald ))
  local iowp=$(( ( iowd * 1000 ) / totald ))

  printf "%s %s %s %s\n" "$pct" "$userp" "$sysp" "$iowp"
}

collect_load(){ awk '{print $1,$2,$3}' /proc/loadavg; }

collect_mem() {
  awk '
    $1=="MemTotal:"{mt=$2}
    $1=="MemAvailable:"{ma=$2}
    $1=="SwapTotal:"{st=$2}
    $1=="SwapFree:"{sf=$2}
    END{print mt,ma,st,sf}
  ' /proc/meminfo
}

collect_disk(){ df -P / | awk 'NR==2{print $2,$3,$4,$5}'; }

secs_to_hms(){
  local s="$1"
  local h=$((s/3600))
  local m=$(((s%3600)/60))
  local sec=$((s%60))
  printf "%02d:%02d:%02d" "$h" "$m" "$sec"
}

collect_tables() {
  local psout
  psout="$(ps -eo pid,user,pcpu,rss,etimes,args --no-headers 2>/dev/null || true)"

  echo "===PROCS==="
  printf "%s\n" "$psout" \
    | awk '{pid=$1; user=$2; cpu=$3; rss=$4; et=$5; $1="";$2="";$3="";$4="";$5=""; sub(/^ +/,""); cmd=$0;
           printf "%s\t%s\t%s\t%s\t%s\t%s\n", pid,user,cpu,rss,et,cmd }' \
    | sort -t $'\t' -k3,3nr | head -n 10

  echo "===ACCOUNTS==="
  printf "%s\n" "$psout" \
    | awk '
      function add(u,cpu,rss,isphp,pool){
        cpuSum[u]+=cpu; rssSum[u]+=rss; procCnt[u]+=1;
        if(isphp){ phpCnt[u]+=1 }
        if(pool!=""){
          poolCpu[u,pool]+=cpu;
          if(poolCpu[u,pool] > bestPoolCpu[u]) { bestPoolCpu[u]=poolCpu[u,pool]; bestPool[u]=pool }
        }
      }
      {
        user=$2; cpu=$3+0; rss=$4+0; et=$5;
        $1="";$2="";$3="";$4="";$5=""; sub(/^ +/,""); cmd=$0;
        pool=""; isphp=0;
        if(cmd ~ /php-fpm: pool /){
          isphp=1;
          sub(/^.*php-fpm: pool /,"",cmd);
          pool=cmd;
        }
        add(user,cpu,rss,isphp,pool);
      }
      END{
        for(u in procCnt){
          top=bestPool[u]; if(top=="") top="-";
          printf "%s\t%.2f\t%d\t%d\t%d\t%s\n", u, cpuSum[u], rssSum[u], phpCnt[u]+0, procCnt[u], top
        }
      }' \
    | sort -t $'\t' -k2,2nr | head -n 10

  echo "===POOLS==="
  printf "%s\n" "$psout" \
    | awk '
      {
        user=$2; cpu=$3+0; rss=$4+0; et=$5+0;
        $1="";$2="";$3="";$4="";$5=""; sub(/^ +/,""); cmd=$0;
        if(cmd ~ /php-fpm: pool /){
          sub(/^.*php-fpm: pool /,"",cmd);
          pool=cmd;
          cpuSum[pool]+=cpu; rssSum[pool]+=rss; workers[pool]+=1; owner[pool]=user;
          if(et > maxEt[pool]) maxEt[pool]=et;
        }
      }
      END{
        for(p in workers){
          printf "%s\t%s\t%.2f\t%d\t%d\t%d\n", p, owner[p], cpuSum[p], rssSum[p], workers[p], maxEt[p]
        }
      }' \
    | sort -t $'\t' -k3,3nr | head -n 15
}

build_metrics_json(){
  ensure_cache_dir
  local now; now="$(now_epoch)"

  local pct userp sysp iowp
  read -r pct userp sysp iowp < <(collect_cpu)

  local l1 l5 l15
  read -r l1 l5 l15 < <(collect_load)

  local mt ma st sf
  read -r mt ma st sf < <(collect_mem)

  local dt du dfree dpct
  read -r dt du dfree dpct < <(collect_disk)
  local dp="${dpct%%%}"

  local tables procs accounts pools
  tables="$(collect_tables)"
  procs="$(printf "%s\n" "$tables" | awk 'BEGIN{p=0} /^===PROCS===/{p=1;next} /^===ACCOUNTS===/{p=0} p{print}')"
  accounts="$(printf "%s\n" "$tables" | awk 'BEGIN{p=0} /^===ACCOUNTS===/{p=1;next} /^===POOLS===/{p=0} p{print}')"
  pools="$(printf "%s\n" "$tables" | awk 'BEGIN{p=0} /^===POOLS===/{p=1;next} p{print}')"

  {
    printf "{"
    printf "\"ts\":%s," "$now"
    printf "\"cpu\":{\"pct\":%s,\"user\":%s,\"sys\":%s,\"iowait\":%s}," "$pct" "$userp" "$sysp" "$iowp"
    printf "\"load\":{\"l1\":%s,\"l5\":%s,\"l15\":%s}," "$l1" "$l5" "$l15"
    printf "\"mem\":{\"mem_total_kb\":%s,\"mem_avail_kb\":%s,\"swap_total_kb\":%s,\"swap_free_kb\":%s}," "$mt" "$ma" "$st" "$sf"
    printf "\"disk\":{\"mount\":\"/\",\"total_kb\":%s,\"used_kb\":%s,\"free_kb\":%s,\"used_pct\":%s}," "$dt" "$du" "$dfree" "$dp"

    printf "\"accounts\":["
    local first=1
    while IFS=$'\t' read -r user cpuSum rssSum phpCnt procCnt topPool; do
      [[ -z "${user}" ]] && continue
      local ju jp
      ju="$(json_escape "$user")"
      jp="$(json_escape "$topPool")"
      if [[ $first -eq 0 ]]; then printf ","; fi
      first=0
      printf "{\"user\":\"%s\",\"cpu\":%.2f,\"rss_kb\":%s,\"php\":%s,\"proc\":%s,\"top_pool\":\"%s\"}" "$ju" "$cpuSum" "$rssSum" "$phpCnt" "$procCnt" "$jp"
    done <<<"$accounts"
    printf "],"

    printf "\"procs\":["
    first=1
    while IFS=$'\t' read -r pid user cpu rss et cmd; do
      [[ -z "${pid}" ]] && continue
      local ju jc hms
      ju="$(json_escape "$user")"
      jc="$(json_escape "$cmd")"
      hms="$(secs_to_hms "$et")"
      if [[ $first -eq 0 ]]; then printf ","; fi
      first=0
      printf "{\"pid\":%s,\"user\":\"%s\",\"cpu\":%.2f,\"rss_kb\":%s,\"elapsed\":\"%s\",\"cmd\":\"%s\"}" "$pid" "$ju" "$cpu" "$rss" "$hms" "$jc"
    done <<<"$procs"
    printf "],"

    printf "\"pools\":["
    first=1
    while IFS=$'\t' read -r pool owner cpuSum rssSum workers maxEt; do
      [[ -z "${pool}" ]] && continue
      local jp jo hms
      jp="$(json_escape "$pool")"
      jo="$(json_escape "$owner")"
      hms="$(secs_to_hms "$maxEt")"
      if [[ $first -eq 0 ]]; then printf ","; fi
      first=0
      printf "{\"pool\":\"%s\",\"owner\":\"%s\",\"cpu\":%.2f,\"rss_kb\":%s,\"workers\":%s,\"max_elapsed\":\"%s\"}" "$jp" "$jo" "$cpuSum" "$rssSum" "$workers" "$hms"
    done <<<"$pools"
    printf "]"

    printf "}"
  } > "${CACHE_FILE}.tmp"
  mv -f "${CACHE_FILE}.tmp" "${CACHE_FILE}"
}

get_metrics_json(){
  ensure_cache_dir
  local now mtime age
  now="$(now_epoch)"
  if [[ -f "${CACHE_FILE}" ]]; then
    mtime="$(file_mtime "${CACHE_FILE}")"
    age=$(( now - mtime ))
  else
    age=$(( CACHE_TTL_SECONDS + 1 ))
  fi

  if [[ "${age}" -gt "${CACHE_TTL_SECONDS}" ]]; then
    build_metrics_json
  fi

  cat "${CACHE_FILE}" 2>/dev/null || echo "{}"
}

render_html(){
  http_header_html
  cat <<'HTML'
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ProcWatch (WHM)</title>
<style>
:root{--bg:#0b1020;--text:#e9ecff;--muted:#a8b0d6;--border:rgba(255,255,255,.08);--shadow:0 12px 30px rgba(0,0,0,.35);--radius:16px;--mono:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New",monospace;--sans:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,Arial}
*{box-sizing:border-box}body{margin:0;font-family:var(--sans);background:radial-gradient(1100px 600px at 20% -10%,rgba(108,92,231,.35),transparent 55%),radial-gradient(900px 500px at 90% 0%,rgba(0,184,148,.25),transparent 50%),radial-gradient(900px 600px at 50% 120%,rgba(255,92,122,.18),transparent 55%),var(--bg);color:var(--text)}
.wrap{max-width:1180px;margin:28px auto;padding:0 18px 36px}header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:18px}
h1{margin:0;font-size:20px;letter-spacing:.2px}.subtitle{margin:6px 0 0;color:var(--muted);font-size:13px;line-height:1.35;max-width:760px}
.meta{display:flex;gap:10px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
.pill{padding:8px 10px;border:1px solid var(--border);background:rgba(255,255,255,.04);border-radius:999px;font-size:12px;color:var(--muted);box-shadow:0 10px 20px rgba(0,0,0,.18);backdrop-filter: blur(6px)}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:14px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.03));border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden}
.hd{padding:14px 16px 10px;display:flex;align-items:center;justify-content:space-between;gap:10px;border-bottom:1px solid var(--border);background:rgba(0,0,0,.08)}
.hd .k{font-weight:650;font-size:13px;letter-spacing:.2px}.hd .t{font-family:var(--mono);font-size:12px;color:var(--muted)}
.bd{padding:14px 16px 16px}.metric{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:4px 0 10px}
.big{font-size:28px;font-weight:750;letter-spacing:.2px}.unit{font-size:12px;color:var(--muted);margin-left:6px}
.right{text-align:right;color:var(--muted);font-size:12px;font-family:var(--mono);line-height:1.35}
.bar{height:10px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.09);border-radius:999px;overflow:hidden}
.bar>span{display:block;height:100%;width:0%;background:linear-gradient(90deg,rgba(53,208,127,.95),rgba(255,204,102,.95),rgba(255,92,122,.95));transition:width .55s ease}
.subgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:10px}
.kv{padding:10px;border:1px solid var(--border);border-radius:12px;background:rgba(0,0,0,.06);display:flex;justify-content:space-between;gap:10px;font-size:12px;color:var(--muted)}
.kv b{color:rgba(233,236,255,.93);font-weight:650;font-family:var(--mono)}
.span-3{grid-column:span 3}.span-6{grid-column:span 6}.span-12{grid-column:span 12}
@media (max-width:980px){.span-3{grid-column:span 6}.span-6{grid-column:span 12}header{flex-direction:column;align-items:flex-start}.meta{justify-content:flex-start}}
@media (max-width:560px){.span-3{grid-column:span 12}.subgrid{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:12px;color:rgba(233,236,255,.93);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px;border-bottom:1px solid var(--border);white-space:nowrap;vertical-align:middle}
th{color:var(--muted);font-weight:650;font-size:11px;letter-spacing:.2px;text-transform:uppercase;background:rgba(0,0,0,.10)}
tbody tr:hover{background:rgba(255,255,255,.04)}.num{font-family:var(--mono);text-align:right}.muted{color:var(--muted);font-family:var(--mono)}
footer{margin-top:14px;color:var(--muted);font-size:12px;line-height:1.45}
</style></head>
<body><div class="wrap">
<header><div><h1>ProcWatch</h1><p class="subtitle">Fast, process-aware snapshots for WHM. Refreshes every 5 seconds. No history (MVP).</p></div>
<div class="meta"><div class="pill">Host: <b id="host">-</b></div><div class="pill">Last update: <b id="ts">-</b></div><div class="pill">Cache TTL: <b>5s</b></div></div>
</header>

<section class="grid">
<div class="card span-3"><div class="hd"><div class="k">CPU</div><div class="t">user/sys/iowait</div></div><div class="bd">
<div class="metric"><div><span class="big" id="cpuPct">-</span><span class="unit">%</span></div><div class="right" id="cpuBreak">-</div></div>
<div class="bar"><span id="cpuBar"></span></div>
<div class="subgrid"><div class="kv"><span>IO wait</span><b id="iowait">-</b></div><div class="kv"><span>Note</span><b>snapshot</b></div></div>
</div></div>

<div class="card span-3"><div class="hd"><div class="k">Memory</div><div class="t">used/total</div></div><div class="bd">
<div class="metric"><div><span class="big" id="memUsed">-</span><span class="unit">GB</span></div><div class="right" id="memMeta">-</div></div>
<div class="bar"><span id="memBar"></span></div>
<div class="subgrid"><div class="kv"><span>Available</span><b id="memAvail">-</b></div><div class="kv"><span>Swap used</span><b id="swapUsed">-</b></div></div>
</div></div>

<div class="card span-3"><div class="hd"><div class="k">Load average</div><div class="t">1/5/15</div></div><div class="bd">
<div class="metric"><div><span class="big" id="l1">-</span><span class="unit">1m</span></div><div class="right" id="loads">-</div></div>
<div class="bar"><span id="loadBar"></span></div>
<div class="subgrid"><div class="kv"><span>Hint</span><b id="loadHint">-</b></div><div class="kv"><span>Note</span><b>relative</b></div></div>
</div></div>

<div class="card span-3"><div class="hd"><div class="k">Disk</div><div class="t">/</div></div><div class="bd">
<div class="metric"><div><span class="big" id="diskPct">-</span><span class="unit">%</span></div><div class="right" id="diskMeta">-</div></div>
<div class="bar"><span id="diskBar"></span></div>
<div class="subgrid"><div class="kv"><span>Used</span><b id="diskUsed">-</b></div><div class="kv"><span>Free</span><b id="diskFree">-</b></div></div>
</div></div>

<div class="card span-6"><div class="hd"><div class="k">Top accounts</div><div class="t">by CPU (snapshot)</div></div><div class="bd" style="padding-top:10px;">
<table><thead><tr><th>User</th><th>Top pool</th><th class="num">CPU%</th><th class="num">RAM</th><th class="num">PHP</th><th class="num">Proc</th></tr></thead><tbody id="tblAccounts"></tbody></table>
</div></div>

<div class="card span-6"><div class="hd"><div class="k">Top processes</div><div class="t">CPU/RAM/elapsed</div></div><div class="bd" style="padding-top:10px;">
<table><thead><tr><th>PID</th><th>User</th><th>Command</th><th class="num">CPU%</th><th class="num">RAM</th><th class="num">Elapsed</th></tr></thead><tbody id="tblProcs"></tbody></table>
</div></div>

<div class="card span-12"><div class="hd"><div class="k">Top PHP-FPM pools</div><div class="t">pool-level view</div></div><div class="bd" style="padding-top:10px;">
<table><thead><tr><th>Pool</th><th>Owner</th><th class="num">CPU%</th><th class="num">RAM</th><th class="num">Workers</th><th class="num">Max elapsed</th></tr></thead><tbody id="tblPools"></tbody></table>
</div></div>
</section>

<footer><div>Tip: This is a live snapshot. History can be added later as an optional module.</div></footer>
</div>

<script>
const fmtGB=(kb)=> (kb/1024/1024).toFixed(2)+" GB";
const fmtMB=(kb)=>{const mb=kb/1024; if(mb>=1024) return (mb/1024).toFixed(2)+" GB"; return mb.toFixed(0)+" MB";};
const pct=(permille)=> (permille/10).toFixed(1);
const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
const loadHint=(l1)=>{ if(l1<0.8) return "OK"; if(l1<2.0) return "Busy"; return "High"; };
async function fetchMetrics(){ const res=await fetch("?action=metrics",{cache:"no-store"}); return await res.json(); }
function setBar(id,val){ document.getElementById(id).style.width=clamp(val,0,100)+"%"; }
function render(m){
  const ts=new Date((m.ts||0)*1000);
  document.getElementById("host").textContent=window.location.hostname||"server";
  document.getElementById("ts").textContent=isNaN(ts.getTime())?"-":ts.toLocaleTimeString();

  document.getElementById("cpuPct").textContent=pct(m.cpu.pct||0);
  document.getElementById("cpuBreak").innerHTML=`user ${pct(m.cpu.user||0)}%<br>sys ${pct(m.cpu.sys||0)}%<br>iowait ${pct(m.cpu.iowait||0)}%`;
  document.getElementById("iowait").textContent=pct(m.cpu.iowait||0)+"%";
  setBar("cpuBar",(m.cpu.pct||0)/10);

  const total=m.mem.mem_total_kb||0, avail=m.mem.mem_avail_kb||0, used=Math.max(0,total-avail);
  document.getElementById("memUsed").textContent=(used/1024/1024).toFixed(1);
  document.getElementById("memMeta").innerHTML=`${fmtGB(used)} / ${fmtGB(total)}<br><span class="muted">${((used/total)*100||0).toFixed(1)}% used</span>`;
  document.getElementById("memAvail").textContent=fmtGB(avail);
  const swapUsed=Math.max(0,(m.mem.swap_total_kb||0)-(m.mem.swap_free_kb||0));
  document.getElementById("swapUsed").textContent=fmtGB(swapUsed);
  setBar("memBar",(used/total)*100||0);

  document.getElementById("l1").textContent=(m.load.l1||0).toFixed(2);
  document.getElementById("loads").textContent=`${(m.load.l1||0).toFixed(2)} / ${(m.load.l5||0).toFixed(2)} / ${(m.load.l15||0).toFixed(2)}`;
  document.getElementById("loadHint").textContent=loadHint(m.load.l1||0);
  setBar("loadBar",Math.min(100,(m.load.l1||0)*25));

  document.getElementById("diskPct").textContent=(m.disk.used_pct||0);
  document.getElementById("diskMeta").textContent=`${fmtGB(m.disk.used_kb||0)} / ${fmtGB(m.disk.total_kb||0)}`;
  document.getElementById("diskUsed").textContent=fmtGB(m.disk.used_kb||0);
  document.getElementById("diskFree").textContent=fmtGB(m.disk.free_kb||0);
  setBar("diskBar",m.disk.used_pct||0);

  const a=document.getElementById("tblAccounts"); a.innerHTML="";
  (m.accounts||[]).forEach(r=>{
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${r.user}</td><td class="muted">${r.top_pool||"-"}</td><td class="num">${(r.cpu||0).toFixed(1)}</td><td class="num">${fmtMB(r.rss_kb||0)}</td><td class="num">${r.php||0}</td><td class="num">${r.proc||0}</td>`;
    a.appendChild(tr);
  });

  const p=document.getElementById("tblProcs"); p.innerHTML="";
  (m.procs||[]).forEach(r=>{
    const cmd=(r.cmd||"").length>52?(r.cmd||"").slice(0,52)+"...":(r.cmd||"");
    const tr=document.createElement("tr");
    tr.innerHTML=`<td class="muted">${r.pid}</td><td>${r.user}</td><td class="muted" title="${(r.cmd||"").replaceAll('"','&quot;')}">${cmd}</td><td class="num">${(r.cpu||0).toFixed(1)}</td><td class="num">${fmtMB(r.rss_kb||0)}</td><td class="num">${r.elapsed||"-"}</td>`;
    p.appendChild(tr);
  });

  const pools=document.getElementById("tblPools"); pools.innerHTML="";
  (m.pools||[]).forEach(r=>{
    const tr=document.createElement("tr");
    tr.innerHTML=`<td>${r.pool}</td><td class="muted">${r.owner}</td><td class="num">${(r.cpu||0).toFixed(1)}</td><td class="num">${fmtMB(r.rss_kb||0)}</td><td class="num">${r.workers||0}</td><td class="num">${r.max_elapsed||"-"}</td>`;
    pools.appendChild(tr);
  });
}
async function tick(){ try{ render(await fetchMetrics()); }catch(e){} }
tick(); setInterval(tick,5000);
</script></body></html>
HTML
}

main(){
  local action=""; action="$(query_param "action" || true)"
  if [[ "$action" == "metrics" ]]; then http_header_json; get_metrics_json; exit 0; fi
  render_html
}
main "$@"
