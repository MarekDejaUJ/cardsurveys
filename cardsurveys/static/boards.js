/* Board widgets: tier board, tier board with an aside region, arrow board, pile
   board, plane board and pairwise questions. Tap a card, then a target. The
   readout lists the statements the arrangement records. */
(function(){
  const root = document.getElementById("board");
  if(!root) return;
  const CS = window.CardStructures;
  const kind = root.dataset.kind;
  const k = parseInt(root.dataset.k || "3", 10);
  const S = JSON.parse(root.dataset.strings || "{}");
  const elements = JSON.parse(root.dataset.elements || "[]");
  const n = elements.length;
  const labels = elements.map(e => e.label);
  let order = elements.map((e, i) => i);
  try { const o = root.dataset.order ? JSON.parse(root.dataset.order) : null; if(Array.isArray(o) && o.length === n) order = o; } catch(e) {}
  const rank = []; order.forEach((i, r) => { rank[i] = r; });
  const area = document.getElementById("boardArea");
  const readout = document.getElementById("readout");
  const hidden = document.getElementById("placementsJson");
  const submit = document.getElementById("submitBoard");
  let selected = null;
  let placements = {};
  let refused = null;

  function tr(key, vars){ let s = S[key] || key; if(vars) for(const v in vars) s = s.split("{" + v + "}").join(vars[v]); return s; }
  function esc(v){ return String(v).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch])); }
  function el(tag, cls, html){ const e = document.createElement(tag); if(cls) e.className = cls; if(html !== undefined) e.innerHTML = html; return e; }

  function chip(i){
    const b = el("button", "chip" + (selected === i ? " sel" : ""));
    b.type = "button"; b.textContent = labels[i];
    b.setAttribute("aria-pressed", selected === i ? "true" : "false");
    b.addEventListener("click", () => { selected = (selected === i ? null : i); render(); });
    return b;
  }
  function tag(i, onRemove){
    const t = el("button", "ptag"); t.type = "button"; t.textContent = labels[i]; t.title = tr("pick_up");
    t.addEventListener("click", ev => { ev.stopPropagation(); onRemove(); });
    return t;
  }
  function trayBlock(){
    const wrap = el("div");
    wrap.appendChild(el("div", "tray-label", esc(tr("unplaced"))));
    const tray = el("div", "tray");
    let any = false;
    order.forEach(i => { if(placements[String(i)] === undefined){ tray.appendChild(chip(i)); any = true; } });
    if(!any) tray.innerHTML = '<span class="empty mono">' + esc(tr("all_placed")) + "</span>";
    wrap.appendChild(tray);
    return wrap;
  }
  function buildTier(){
    area.innerHTML = "";
    area.appendChild(trayBlock());
    const strata = el("div", "strata");
    for(let r = k - 1; r >= 0; r--){
      const row = el("div", "stratum" + (selected !== null ? " target" : ""));
      row.dataset.tier = r;
      const name = r === 0 ? tr("row_first") : (r === k - 1 ? tr("row_last", {n: k}) : tr("row_n", {n: r + 1}));
      row.appendChild(el("div", "stratum-head", '<span class="stratum-name">' + esc(name) + '</span><span class="depthmark">' + esc(tr("same_row")) + "</span>"));
      const placed = el("div", "placed");
      order.forEach(i => { if(placements[String(i)] === r) placed.appendChild(tag(i, () => { delete placements[String(i)]; selected = i; render(); })); });
      row.appendChild(placed);
      row.addEventListener("click", () => { if(selected !== null){ placements[String(selected)] = r; selected = null; render(); } });
      strata.appendChild(row);
    }
    area.appendChild(strata);
    if(kind === "tier_aside"){
      const aside = el("div", "sidebin" + (selected !== null ? " target" : ""));
      aside.dataset.tier = "aside";
      aside.appendChild(el("div", "stratum-head", '<span class="stratum-name">' + esc(tr("aside")) + '</span><span class="depthmark">' + esc(tr("aside_note")) + "</span>"));
      const placed = el("div", "placed");
      order.forEach(i => { if(placements[String(i)] === "aside") placed.appendChild(tag(i, () => { delete placements[String(i)]; selected = i; render(); })); });
      aside.appendChild(placed);
      aside.addEventListener("click", () => { if(selected !== null){ placements[String(selected)] = "aside"; selected = null; render(); } });
      area.appendChild(aside);
    }
    area.appendChild(el("p", "aside-note", esc(tr("tier_note"))));
  }
  function buildPile(){
    area.innerHTML = "";
    area.appendChild(trayBlock());
    const piles = el("div", "piles");
    for(let p = 0; p < n; p++){
      const pile = el("div", "pile" + (selected !== null ? " target" : ""));
      pile.dataset.pile = p;
      pile.appendChild(el("span", "stratum-name", esc(tr("pile_n", {n: p + 1}))));
      const placed = el("div", "placed");
      order.forEach(i => { if(placements[String(i)] === "p" + p) placed.appendChild(tag(i, () => { delete placements[String(i)]; selected = i; render(); })); });
      pile.appendChild(placed);
      pile.addEventListener("click", () => { if(selected !== null){ placements[String(selected)] = "p" + p; selected = null; render(); } });
      piles.appendChild(pile);
    }
    area.appendChild(piles);
    area.appendChild(el("p", "aside-note", esc(tr("pile_note"))));
  }
  const SVGNS = "http://www.w3.org/2000/svg";
  function svgEl(tagName, attrs){ const e = document.createElementNS(SVGNS, tagName); for(const a in attrs) e.setAttribute(a, attrs[a]); return e; }
  function buildArrow(){
    area.innerHTML = "";
    const W = 520, H = 340, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 56;
    const svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, class: "boardsvg", role: "img"});
    const defs = svgEl("defs", {});
    const mk = (id, color) => { const m = svgEl("marker", {id, viewBox: "0 0 10 10", refX: "10", refY: "5", markerWidth: "8", markerHeight: "8", orient: "auto-start-reverse"}); m.appendChild(svgEl("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: color})); return m; };
    defs.appendChild(mk("head", "#C0703C")); defs.appendChild(mk("headgrey", "#8497A4"));
    svg.appendChild(defs);
    const pos = elements.map((e, i) => { const ang = -Math.PI / 2 + 2 * Math.PI * rank[i] / n; return [cx + R * Math.cos(ang), cy + R * Math.sin(ang)]; });
    const drawn = CS.fromPairs(placements.arrows || []);
    const closed = CS.closure(drawn, n);
    const line = (i, j, implied) => {
      const [x1, y1] = pos[i], [x2, y2] = pos[j];
      const dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, pad = 44;
      svg.appendChild(svgEl("line", {x1: x1 + ux * pad, y1: y1 + uy * pad, x2: x2 - ux * pad, y2: y2 - uy * pad, class: "arrow" + (implied ? " implied" : "")}));
    };
    for(const [i, j] of CS.toPairs(closed)) if(!drawn.has(CS.key(i, j))) line(i, j, true);
    for(const [i, j] of CS.toPairs(drawn)) line(i, j, false);
    elements.forEach((e, i) => {
      const g = svgEl("g", {class: "card" + (selected === i ? " sel" : ""), transform: "translate(" + pos[i][0] + "," + pos[i][1] + ")", "data-card": i, tabindex: "0"});
      const w = Math.max(72, 8 * labels[i].length + 20);
      g.appendChild(svgEl("rect", {x: -w / 2, y: -18, width: w, height: 36, rx: 2}));
      const t = svgEl("text", {x: 0, y: 4, "text-anchor": "middle"}); t.textContent = labels[i]; g.appendChild(t);
      g.addEventListener("click", () => {
        refused = null;
        if(selected === null) selected = i;
        else if(selected === i) selected = null;
        else {
          const arrows = (placements.arrows || []).slice();
          if(!arrows.some(a => a[0] === selected && a[1] === i)){
            const trial = CS.fromPairs(arrows.concat([[selected, i]]));
            if(CS.isAcyclic(trial, n)){ arrows.push([selected, i]); placements = {arrows}; }
            else refused = [selected, i];
          }
          selected = null;
        }
        render();
      });
      svg.appendChild(g);
    });
    area.appendChild(el("div", "tray-label", esc(tr("arrow_hint"))));
    area.appendChild(svg);
    const list = el("div", "arrowlist");
    (placements.arrows || []).forEach(([i, j], idx) => {
      const t = el("button", "ptag"); t.type = "button"; t.textContent = labels[i] + " → " + labels[j]; t.title = tr("erase");
      t.addEventListener("click", () => { const arrows = placements.arrows.slice(); arrows.splice(idx, 1); placements = {arrows}; refused = null; render(); });
      list.appendChild(t);
    });
    if(!(placements.arrows || []).length) list.innerHTML = '<span class="empty mono">' + esc(tr("no_arrows")) + "</span>";
    area.appendChild(list);
    area.appendChild(el("p", "aside-note", esc(tr("arrow_note"))));
  }
  function buildPlane(){
    area.innerHTML = "";
    area.appendChild(trayBlock());
    const W = 480, H = 360, pad = 36;
    const svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, class: "boardsvg plane"});
    for(let g = 0; g <= 8; g++){
      const x = pad + (W - 2 * pad) * g / 8, y = pad + (H - 2 * pad) * g / 8;
      svg.appendChild(svgEl("line", {x1: x, y1: pad, x2: x, y2: H - pad, class: "grid"}));
      svg.appendChild(svgEl("line", {x1: pad, y1: y, x2: W - pad, y2: y, class: "grid"}));
    }
    const ax = svgEl("text", {x: W - pad, y: H - 10, "text-anchor": "end", class: "axis"}); ax.textContent = tr("plane_after"); svg.appendChild(ax);
    const ay = svgEl("text", {x: pad, y: 20, class: "axis"}); ay.textContent = tr("plane_before"); svg.appendChild(ay);
    svg.addEventListener("click", ev => {
      if(selected === null) return;
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      const x = Math.min(Math.max(p.x, pad), W - pad), y = Math.min(Math.max(p.y, pad), H - pad);
      placements[String(selected)] = [Math.round(x), Math.round(H - y)];
      selected = null; render();
    });
    elements.forEach((e, i) => {
      const p = placements[String(i)]; if(!p) return;
      const cx = p[0], cy = H - p[1];
      const dot = svgEl("circle", {cx, cy, r: 9, class: "dot"});
      dot.addEventListener("click", ev => { ev.stopPropagation(); delete placements[String(i)]; selected = i; render(); });
      svg.appendChild(dot);
      const t = svgEl("text", {x: cx + 12, y: cy + 4, class: "dotlabel"}); t.textContent = labels[i]; svg.appendChild(t);
    });
    area.appendChild(svg);
    area.appendChild(el("p", "aside-note", esc(tr("plane_note"))));
  }
  function buildPairs(){
    area.innerHTML = "";
    area.appendChild(el("div", "tray-label", esc(tr("pairs_hint"))));
    const shown = [];
    for(let p = 0; p < n; p++) for(let q = p + 1; q < n; q++) shown.push([order[p], order[q]]);
    for(const [x, y] of shown){
      const i = Math.min(x, y), j = Math.max(x, y);
      const row = el("div", "pairrow");
      row.appendChild(el("div", "pairname", esc(labels[x]) + " " + esc(tr("and")) + " " + esc(labels[y])));
      const seg = el("div", "seg");
      const cur = placements[CS.key(i, j)];
      const first = u => (u === i ? "a" : "b");
      [[first(x), labels[x] + " " + tr("before") + " " + labels[y]], [first(y), labels[y] + " " + tr("before") + " " + labels[x]], ["apart", tr("unrelated")], ["undecided", tr("cannot_decide")]].forEach(([v, txt]) => {
        const b = el("button", cur === v ? "on" : ""); b.type = "button"; b.textContent = txt; b.dataset.value = v;
        b.addEventListener("click", () => { placements[CS.key(i, j)] = v; render(); });
        seg.appendChild(b);
      });
      row.appendChild(seg);
      area.appendChild(row);
    }
  }
  function relRow(a, op, b, cls, tagText){
    return '<div class="rel"><span class="a">' + esc(a) + '</span><span class="op ' + cls + '">' + op + '</span><span class="b">' + esc(b) + '</span><span class="tag">' + esc(tagText) + "</span></div>";
  }
  function renderReadout(){
    const done = CS.complete(kind, n, placements);
    const anyPlaced = kind === "arrow" ? true : Object.keys(placements).length > 0;
    if(!anyPlaced){ readout.innerHTML = '<div class="empty">' + esc(tr("place_to_see")) + "</div>"; if(submit) submit.disabled = true; if(hidden) hidden.value = ""; return; }
    const r = CS.reading(kind, n, placements, k);
    let html = "<h3>" + esc(tr("statements")) + "</h3>";
    const sts = CS.states(r.structure, n, r.judgments);
    let count = 0;
    for(const s of sts){
      const a = labels[s.a], b = labels[s.b];
      if(r.judgments === "sim"){
        if(s.state === "tie"){ html += relRow(a, "~", b, "sim", tr("same_pile")); count++; } else html += relRow(a, "||", b, "inc", tr("apart"));
      } else if(s.state === "a_prec_b" || s.state === "b_prec_a"){
        const [x, y] = s.state === "a_prec_b" ? [a, b] : [b, a];
        const implied = kind === "arrow" && r.drawn && !r.drawn.has(CS.key(s.state === "a_prec_b" ? s.a : s.b, s.state === "a_prec_b" ? s.b : s.a));
        html += relRow(x, "≺", y, implied ? "imp" : "prec", implied ? tr("implied") : tr("before")); count++;
      } else if(kind === "pairs" && placements[CS.key(s.a, s.b)] === "undecided"){
        html += relRow(a, "?", b, "inc", tr("cannot_decide_rec"));
      } else {
        const placedBoth = kind === "arrow" || kind === "pairs" || (placements[String(s.a)] !== undefined && placements[String(s.b)] !== undefined);
        if(placedBoth) html += relRow(a, "||", b, "inc", tr("apart"));
      }
    }
    if(refused) html += '<div class="line bad">' + esc(tr("refused", {a: labels[refused[0]], b: labels[refused[1]]})) + "</div>";
    if(done){
      if(r.judgments === "sim") html += '<div class="line ok">' + esc(tr("partition", {together: count, apart: sts.length - count})) + "</div>";
      else if(r.coherent) html += '<div class="line ok">' + esc(tr("coherent", {count: count, total: sts.length})) + "</div>";
      else html += '<div class="line bad">' + esc(tr("incoherent")) + "</div>";
    } else html += '<div class="line">' + esc(tr("place_every")) + "</div>";
    readout.innerHTML = html;
    if(hidden) hidden.value = done ? JSON.stringify(placements) : "";
    if(submit) submit.disabled = !done || (!r.coherent && kind !== "pairs");
  }
  function render(){
    if(kind === "tier" || kind === "tier_aside") buildTier();
    else if(kind === "arrow") buildArrow();
    else if(kind === "pile") buildPile();
    else if(kind === "plane") buildPlane();
    else buildPairs();
    renderReadout();
  }
  const reset = document.getElementById("resetBoard");
  if(reset) reset.addEventListener("click", () => { placements = {}; selected = null; refused = null; render(); });
  const form = document.getElementById("boardForm");
  if(form) form.addEventListener("submit", ev => { if(!CS.complete(kind, n, placements)){ ev.preventDefault(); renderReadout(); } });
  if(root.dataset.initial){ try { const p0 = JSON.parse(root.dataset.initial); if(p0 && typeof p0 === "object") placements = p0; } catch(e) {} }
  render();
})();
