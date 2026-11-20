/* Tap-order blocks: tap the cards of a block in order (first tap first). A block
   opened again with the Back button shows the order given before (data-initial). An
   anchor card, when the task has one, is ordered like any other card. When the
   anchor closes the block (data-closes="1"), tapping the anchor ends the order:
   the cards left untapped lie below the anchor, tied with one another, and the
   anchor is placed after the last card when every other card is tapped. */
(function(){
  const root = document.getElementById("tapTask");
  if(!root) return;
  const S = JSON.parse(root.dataset.strings || "{}");
  const cards = JSON.parse(root.dataset.cards || "[]");
  const area = document.getElementById("tapArea");
  const seqBox = document.getElementById("tapSequence");
  const hidden = document.getElementById("resultJson");
  const eventsField = document.getElementById("eventsJson");
  const msField = document.getElementById("blockMs");
  const submit = document.getElementById("submitBlock");
  const gateInputs = Array.from(document.querySelectorAll("input[name=gate]"));
  const t0 = performance.now();
  const anchor = (cards.find(c => c.anchor) || {}).code || null;
  const closes = root.dataset.closes === "1" && anchor !== null;
  let sequence = [];
  let autoAnchor = false;
  const events = [];
  const demo = root.dataset.mode === "demo";
  try {
    const initial = JSON.parse(root.dataset.initial || "null");
    if(Array.isArray(initial) && initial.length && initial.every(code => cards.some(c => c.code === code))){
      sequence = initial.slice();
      autoAnchor = closes && sequence[sequence.length - 1] === anchor && cards.every(c => sequence.indexOf(c.code) >= 0);
      events.push(["restored", 0]);
    }
  } catch(e) {}

  function tr(key, vars){ let s = S[key] || key; if(vars) for(const v in vars) s = s.split("{" + v + "}").join(vars[v]); return s; }
  function esc(v){ return String(v).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch])); }
  function el(tag, cls, html){ const e = document.createElement(tag); if(cls) e.className = cls; if(html !== undefined) e.innerHTML = html; return e; }
  function now(){ return Math.round(performance.now() - t0); }
  function closed(){ return closes && sequence.indexOf(anchor) >= 0; }
  function complete(){ return closes ? closed() : sequence.length === cards.length; }

  function tap(code){
    if(sequence.indexOf(code) >= 0 || closed()) return;
    sequence.push(code); events.push([code, now()]);
    if(closes && code !== anchor && cards.every(c => c.code === anchor || sequence.indexOf(c.code) >= 0)){
      sequence.push(anchor); events.push(["auto", now()]); autoAnchor = true;
    }
    render();
  }

  function render(){
    area.innerHTML = "";
    const grid = el("div", "tapgrid");
    const isClosed = closed();
    cards.forEach(c => {
      const pos = sequence.indexOf(c.code);
      const tied = isClosed && pos < 0;
      const b = el("button", "tapcard" + (c.anchor ? " anchor" : "") + (c.attention ? " attention" : "") + (pos >= 0 ? " done" : "") + (tied ? " tied" : ""));
      b.type = "button"; b.dataset.code = c.code;
      const mark = pos >= 0 ? '<span class="tapno">' + (pos + 1) + "</span>" : tied ? '<span class="tapno tie">=</span>' : '<span class="tapno empty"></span>';
      b.innerHTML = mark + '<span class="taplabel">' + esc(c.label) + "</span>";
      b.disabled = pos >= 0 || tied;
      b.setAttribute("aria-label", c.label + (pos >= 0 ? " — " + tr("position", {n: pos + 1}) : tied ? " — " + tr("tied") : ""));
      b.addEventListener("click", () => tap(c.code));
      grid.appendChild(b);
    });
    area.appendChild(grid);
    if(sequence.length){
      let html = '<div class="section-label">' + esc(tr("your_order")) + '</div><ol class="taplist">';
      sequence.forEach(code => { const c = cards.find(x => x.code === code); html += "<li" + (c.anchor ? ' class="anchor"' : "") + ">" + esc(c.label) + "</li>"; });
      const rest = isClosed ? cards.filter(c => sequence.indexOf(c.code) < 0) : [];
      if(rest.length) html += '<li class="tied">' + esc(tr("tied")) + ": " + rest.map(c => esc(c.label)).join(", ") + "</li>";
      seqBox.innerHTML = html + "</ol>";
    } else seqBox.innerHTML = '<div class="empty">' + esc(tr("tap_first")) + "</div>";
    const done = complete();
    hidden.value = done ? JSON.stringify(sequence) : "";
    const gateOk = !gateInputs.length || gateInputs.some(i => i.checked);
    if(submit) submit.disabled = !(done && gateOk);
    document.getElementById("undoTap").disabled = !sequence.length;
  }
  document.getElementById("undoTap").addEventListener("click", () => {
    if(!sequence.length) return;
    if(autoAnchor){ sequence.pop(); autoAnchor = false; }
    sequence.pop(); events.push(["undo", now()]); render();
  });
  document.getElementById("resetTap").addEventListener("click", () => { sequence = []; autoAnchor = false; events.push(["reset", now()]); render(); });
  gateInputs.forEach(i => i.addEventListener("change", render));
  const form = document.getElementById("blockForm");
  if(form) form.addEventListener("submit", ev => {
    if(demo){ ev.preventDefault(); return; }
    if(!complete()){ ev.preventDefault(); return; }
    eventsField.value = JSON.stringify(events);
    msField.value = String(now());
  });
  render();
})();
