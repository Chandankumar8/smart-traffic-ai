const $ = (id) => document.getElementById(id);
const MAX_BAR = 12;
let laneKey = "";

function buildButtons(lanes) {
  const box = $("emergency-buttons");
  box.innerHTML = "";
  [...lanes.map(l => l.name), null].forEach(name => {
    const b = document.createElement("button");
    b.textContent = name ?? "Clear";
    b.dataset.lane = name ?? "";
    b.onclick = () => fetch("/api/emergency", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lane: name })
    });
    box.appendChild(b);
  });
}

function render(d) {
  $("total").textContent = d.total;
  $("active").textContent = d.active + (d.phase === "YELLOW" ? " (yellow)" : "");
  $("remaining").textContent = d.remaining + "s";
  $("fps").textContent = d.fps;

  $("lanes").innerHTML = d.lanes.map(l => `
    <div class="card ${l.congested ? "congested" : ""}">
      <div class="lane">
        <span class="light ${l.state}"></span>
        <span class="name">${l.name}</span>
        ${l.emergency ? '<span class="badge">EMERGENCY</span>' : ""}
        <span>${l.count}</span>
      </div>
      <small>avg wait ${l.avg_wait}s · served ${l.throughput}</small>
      <div class="bar"><i style="width:${Math.min(100, l.count / MAX_BAR * 100)}%"></i></div>
    </div>`).join("");

  const key = d.lanes.map(l => l.name).join("|");
  if (key !== laneKey) { buildButtons(d.lanes); laneKey = key; }
  const c = d.comparison || {};
  $("cmp-a").textContent = c.adaptive_avg_waiting ?? "–";
  $("cmp-f").textContent = c.fixed_avg_waiting ?? "–";
  const imp = $("cmp-i");
  if (c.improvement_pct == null) { imp.textContent = "measuring…"; imp.style.color = ""; }
  else {
    const better = c.improvement_pct >= 0;
    imp.textContent = Math.abs(c.improvement_pct) + "% " + (better ? "less waiting" : "more waiting");
    imp.style.color = better ? "var(--green)" : "var(--red)";
  }
  const current = d.lanes.find(l => l.emergency)?.name ?? "";
  document.querySelectorAll("#emergency-buttons button")
    .forEach(b => b.classList.toggle("on", b.dataset.lane === current && current !== ""));
}

async function poll() {
  const status = $("status");
  try {
    const d = await (await fetch("/api/stats")).json();
    if (d.error) { status.textContent = d.error; status.className = "pill err"; }
    else { status.textContent = "live"; status.className = "pill ok"; }
    render(d);
  } catch { status.textContent = "offline"; status.className = "pill err"; }
}
poll(); setInterval(poll, 1000);