/* Time on the page for every survey screen, and questions shown only when an
   earlier question of the same form has a given answer. */
(function(){
  const t0 = performance.now();
  document.querySelectorAll("form.screen-form").forEach(form => {
    form.addEventListener("submit", () => {
      const field = form.querySelector("input[name=client_ms]");
      if(field) field.value = String(Math.round(performance.now() - t0));
    });
  });
  const conditional = Array.from(document.querySelectorAll("[data-cond]"));
  if(!conditional.length) return;
  function valueOf(name){
    const inputs = Array.from(document.querySelectorAll("[name='" + name + "']"));
    if(!inputs.length) return null;
    if(inputs[0].type === "radio") { const c = inputs.find(i => i.checked); return c ? [c.value] : []; }
    if(inputs[0].type === "checkbox") return inputs.filter(i => i.checked).map(i => i.value);
    return inputs[0].value ? [inputs[0].value] : [];
  }
  function holds(c){
    if(!c) return true;
    if(c.all) return c.all.every(holds);
    if(c.any) return c.any.some(holds);
    if(c.not) return !holds(c.not);
    if(!c.answer) return true;
    const have = valueOf(c.answer);
    if(have === null) return true;
    const want = Array.isArray(c.value) ? c.value.map(String) : (c.value === undefined ? [] : [String(c.value)]);
    const op = c.op || "eq";
    if(op === "answered") return have.length > 0;
    if(op === "empty") return have.length === 0;
    if(op === "eq") return have.includes(want[0]);
    if(op === "ne") return !have.includes(want[0]);
    if(op === "in") return have.some(x => want.includes(x));
    if(op === "not_in") return have.length > 0 && !have.some(x => want.includes(x));
    return true;
  }
  function update(){
    conditional.forEach(el => {
      let c = null; try { c = JSON.parse(el.dataset.cond); } catch(e) {}
      const show = holds(c);
      el.classList.toggle("hidden", !show);
      el.querySelectorAll("input,select,textarea").forEach(i => { i.disabled = !show; });
    });
  }
  document.addEventListener("change", update);
  document.addEventListener("input", update);
  update();
})();
document.querySelectorAll("[data-confirm]").forEach(btn => {
  btn.addEventListener("click", ev => { if(!window.confirm(btn.dataset.confirm)) ev.preventDefault(); });
});
