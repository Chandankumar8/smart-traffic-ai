const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
const COLORS = ["#22c55e", "#38bdf8", "#f59e0b", "#e879f9", "#f87171", "#a3e635", "#2dd4bf", "#fb923c"];
let lanes = [], sel = 0, img = new Image();

const msg = (t, err) => { const m = document.getElementById("msg"); m.textContent = t; m.style.color = err ? "#f87171" : "#22c55e"; };

function draw() {
  if (!img.complete || !img.naturalWidth) return;
  ctx.drawImage(img, 0, 0, cv.width, cv.height);
  lanes.forEach((l, i) => {
    const c = COLORS[i % COLORS.length], p = l.points.map(([x, y]) => [x * cv.width, y * cv.height]);
    if (!p.length) return;
    ctx.beginPath(); p.forEach(([x, y], k) => k ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
    if (p.length >= 3) ctx.closePath();
    ctx.fillStyle = c + (i === sel ? "55" : "22"); if (p.length >= 3) ctx.fill();
    ctx.strokeStyle = c; ctx.lineWidth = i === sel ? 3 : 2; ctx.stroke();
    p.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, 5, 0, 7); ctx.fillStyle = c; ctx.fill(); });
    ctx.fillStyle = "#fff"; ctx.font = "bold 18px system-ui"; ctx.fillText(l.name, p[0][0] + 8, p[0][1] + 22);
  });
}

function rows() {
  const box = document.getElementById("rows"); box.innerHTML = "";
  lanes.forEach((l, i) => {
    const r = document.createElement("div"); r.className = "laneRow" + (i === sel ? " sel" : "");
    r.innerHTML = `<input type="radio" name="lane" ${i === sel ? "checked" : ""}>
      <input type="text" value="${l.name}" maxlength="20"><small>${l.points.length} pts</small>
      <button title="Delete lane">✕</button>`;
    r.querySelector("input[type=radio]").onclick = () => { sel = i; rows(); draw(); };
    r.querySelector("input[type=text]").oninput = e => { l.name = e.target.value; draw(); };
    r.querySelector("button").onclick = () => { lanes.splice(i, 1); sel = Math.max(0, sel - 1); rows(); draw(); };
    box.appendChild(r);
  });
}

cv.onclick = e => {
  if (!lanes[sel]) return;
  const b = cv.getBoundingClientRect();
  lanes[sel].points.push([Math.min(1, Math.max(0, (e.clientX - b.left) / b.width)),
                          Math.min(1, Math.max(0, (e.clientY - b.top) / b.height))]);
  rows(); draw();
};
document.getElementById("add").onclick = () => { lanes.push({ name: "Lane " + (lanes.length + 1), points: [] }); sel = lanes.length - 1; rows(); draw(); };
document.getElementById("undo").onclick = () => { lanes[sel]?.points.pop(); rows(); draw(); };
document.getElementById("clear").onclick = () => { if (lanes[sel]) lanes[sel].points = []; rows(); draw(); };
document.getElementById("save").onclick = async () => {
  const r = await fetch("/api/lanes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(lanes) });
  const d = await r.json();
  d.error ? msg(d.error, true) : msg("Saved. The dashboard is now using these lanes.");
};

async function init() {
  lanes = await (await fetch("/api/lanes")).json();
  img.onload = () => { cv.width = img.naturalWidth; cv.height = img.naturalHeight; draw(); };
  img.onerror = () => msg("No video frame yet - wait a moment and reload.", true);
  img.src = "/snapshot.jpg?" + Date.now();
  rows();
}
init();
