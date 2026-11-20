/* Subjective Order Blocks: sort the items of a block into k levels (a lower
   level is a foundation for a higher one) or into the side bin. */
(function(){
  const root = document.getElementById("sobTask");
  if(!root) return;
  const S = JSON.parse(root.dataset.strings || "{}");
  const cards = JSON.parse(root.dataset.cards || "[]");
  const k = cards.length;
  const area = document.getElementById("sobArea");
  const readout = document.getElementById("readout");
  const hidden = document.getElementById("resultJson");
  const eventsField = document.getElementById("eventsJson");
  const msField = document.getElementById("blockMs");
  const submit = document.getElementById("submitBlock");
  const t0 = performance.now();
  let selected = null;
  let placements = {};
  const events = [];

  function tr(key, vars){ let s = S[key] || key; if(vars) for(const v in vars) s = s.split("{" + v + "}").join(vars[v]); return s; }
  function esc(v){ return String(v).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch])); }
  function el(tag, cls, html){ const e = document.createElement(tag); if(cls) e.className = cls; if(html !== undefined) e.innerHTML = html; return e; }
  function now(){ return Math.round(performance.now() - t0); }
  const label = code => (cards.find(c => c.code === code) || {label: code}).label;

  function place(value){
    if(selected === null) return;
    placements[selected] = value;
    events.push([selected, value, now()]);
    selected = null;
    render();
  }
  function build(){
    area.innerHTML = "";
    area.appendChild(el("div", "tray-label", esc(tr("unplaced"))));
    const tray = el("div", "tray");
    let any = false;
    cards.forEach(c => {
      if(placements[c.code] !== undefined) return;
      any = true;
      const b = el("button", "chip" + (selected === c.code ? " sel" : "")); b.type = "button"; b.textContent = c.label; b.dataset.code = c.code;
      b.setAttribute("aria-pressed", selected === c.code ? "true" : "false");
      b.addEventListener("click", () => { selected = (selected === c.code ? null : c.code); render(); });
      tray.appendChild(b);
    });
    if(!any) tray.innerHTML = '<span class="empty mono">' + esc(tr("all_placed")) + "</span>";
    area.appendChild(tray);
    const strata = el("div", "strata");
    for(let r = k - 1; r >= 0; r--){
      const row = el("div", "stratum" + (selected !== null ? " target" : ""));
      row.dataset.tier = r;
      const name = r === 0 ? tr("level_first") : (r === k - 1 ? tr("level_last", {n: k}) : tr("level_n", {n: r + 1}));
      row.appendChild(el("div", "stratum-head", '<span class="stratum-name">' + esc(name) + "</span>"));
      const placed = el("div", "placed");
      cards.forEach(c => { if(placements[c.code] === r){ const t = el("button", "ptag"); t.type = "button"; t.textContent = c.label; t.title = tr("pick_up"); t.addEventListener("click", ev => { ev.stopPropagation(); delete placements[c.code]; events.push([c.code, "lift", now()]); selected = c.code; render(); }); placed.appendChild(t); } });
      row.appendChild(placed);
      row.addEventListener("click", () => place(r));
      strata.appendChild(row);
    }
    area.appendChild(strata);
    const side = el("div", "sidebin" + (selected !== null ? " target" : ""));
    side.dataset.tier = "side";
    side.appendChild(el("div", "stratum-head", '<span class="stratum-name">' + esc(root.dataset.sideLabel || tr("side")) + '</span><span class="depthmark">' + esc(tr("side_note")) + "</span>"));
    const placedSide = el("div", "placed");
    cards.forEach(c => { if(placements[c.code] === "side"){ const t = el("button", "ptag"); t.type = "button"; t.textContent = c.label; t.addEventListener("click", ev => { ev.stopPropagation(); delete placements[c.code]; events.push([c.code, "lift", now()]); selected = c.code; render(); }); placedSide.appendChild(t); } });
    side.appendChild(placedSide);
    side.addEventListener("click", () => place("side"));
    area.appendChild(side);
  }
  function renderReadout(){
    const placed = cards.map(c => c.code).filter(code => placements[code] !== undefined);
    if(placed.length < 2){ readout.innerHTML = '<div class="empty">' + esc(tr("place_to_see")) + "</div>"; }
    else {
      let html = "<h3>" + esc(tr("observations")) + "</h3>";
      for(let a = 0; a < placed.length; a++) for(let b = a + 1; b < placed.length; b++){
        const i = placed[a], j = placed[b], pi = placements[i], pj = placements[j];
        if(pi === "side" || pj === "side" || pi === pj) html += '<div class="rel"><span class="a">' + esc(label(i)) + '</span><span class="op inc">||</span><span class="b">' + esc(label(j)) + '</span><span class="tag">' + esc(tr("incomparable")) + "</span></div>";
        else { const [x, y] = pi < pj ? [i, j] : [j, i]; html += '<div class="rel"><span class="a">' + esc(label(x)) + '</span><span class="op prec">≺</span><span class="b">' + esc(label(y)) + '</span><span class="tag">' + esc(tr("foundation")) + "</span></div>"; }
      }
      readout.innerHTML = html;
    }
    const done = cards.every(c => placements[c.code] !== undefined);
    hidden.value = done ? JSON.stringify(placements) : "";
    submit.disabled = !done;
  }
  function render(){ build(); renderReadout(); }
  document.getElementById("resetBlock").addEventListener("click", () => { placements = {}; selected = null; events.push(["reset", "", now()]); render(); });
  document.getElementById("blockForm").addEventListener("submit", ev => {
    if(!cards.every(c => placements[c.code] !== undefined)){ ev.preventDefault(); return; }
    eventsField.value = JSON.stringify(events);
    msField.value = String(now());
  });
  if(root.dataset.initial){ try { const p0 = JSON.parse(root.dataset.initial); if(p0 && typeof p0 === "object" && !Array.isArray(p0)){ placements = p0; events.push(["restored", "", 0]); } } catch(e) {} }
  render();
})();
