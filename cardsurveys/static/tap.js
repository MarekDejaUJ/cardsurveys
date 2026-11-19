/* Tap-order blocks: tap the cards of a block in order (first tap first). An
   anchor card, when the task has one, is ordered like any other card. */
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
  let sequence = [];
  const events = [];
  const demo = root.dataset.mode === "demo";

  function tr(key, vars){ let s = S[key] || key; if(vars) for(const v in vars) s = s.split("{" + v + "}").join(vars[v]); return s; }
  function esc(v){ return String(v).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch])); }
  function el(tag, cls, html){ const e = document.createElement(tag); if(cls) e.className = cls; if(html !== undefined) e.innerHTML = html; return e; }
  function now(){ return Math.round(performance.now() - t0); }

  function render(){
    area.innerHTML = "";
    const grid = el("div", "tapgrid");
    cards.forEach(c => {
      const pos = sequence.indexOf(c.code);
      const b = el("button", "tapcard" + (c.anchor ? " anchor" : "") + (c.attention ? " attention" : "") + (pos >= 0 ? " done" : ""));
      b.type = "button"; b.dataset.code = c.code;
      b.innerHTML = (pos >= 0 ? '<span class="tapno">' + (pos + 1) + "</span>" : '<span class="tapno empty"></span>') + '<span class="taplabel">' + esc(c.label) + "</span>";
      b.disabled = pos >= 0;
      b.setAttribute("aria-label", c.label + (pos >= 0 ? " — " + tr("position", {n: pos + 1}) : ""));
      b.addEventListener("click", () => { if(sequence.indexOf(c.code) < 0){ sequence.push(c.code); events.push([c.code, now()]); render(); } });
      grid.appendChild(b);
    });
    area.appendChild(grid);
    if(sequence.length){
      let html = '<div class="section-label">' + esc(tr("your_order")) + '</div><ol class="taplist">';
      sequence.forEach(code => { const c = cards.find(x => x.code === code); html += "<li" + (c.anchor ? ' class="anchor"' : "") + ">" + esc(c.label) + "</li>"; });
      seqBox.innerHTML = html + "</ol>";
    } else seqBox.innerHTML = '<div class="empty">' + esc(tr("tap_first")) + "</div>";
    const done = sequence.length === cards.length;
    hidden.value = done ? JSON.stringify(sequence) : "";
    const gateOk = !gateInputs.length || gateInputs.some(i => i.checked);
    if(submit) submit.disabled = !(done && gateOk);
    document.getElementById("undoTap").disabled = !sequence.length;
  }
  document.getElementById("undoTap").addEventListener("click", () => { if(sequence.length){ sequence.pop(); events.push(["undo", now()]); render(); } });
  document.getElementById("resetTap").addEventListener("click", () => { sequence = []; events.push(["reset", now()]); render(); });
  gateInputs.forEach(i => i.addEventListener("change", render));
  const form = document.getElementById("blockForm");
  if(form) form.addEventListener("submit", ev => {
    if(demo){ ev.preventDefault(); return; }
    if(sequence.length !== cards.length){ ev.preventDefault(); return; }
    eventsField.value = JSON.stringify(events);
    msField.value = String(now());
  });
  render();
})();
