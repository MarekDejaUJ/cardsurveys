/* Order structures in the browser. A structure is a Set of "i,j" strings: on
   ordered pairs "i,j" means card i comes before card j; on unordered pairs (pile
   board) "i,j" with i < j means the two cards belong together. The functions
   mirror cardsurveys/engine/structures.py. */
const CardStructures = (function(){
  const key = (i, j) => i + "," + j;
  function pairs(n){ const out = []; for(let i = 0; i < n; i++) for(let j = 0; j < n; j++) if(i !== j) out.push([i, j]); return out; }
  function upairs(n){ const out = []; for(let i = 0; i < n; i++) for(let j = i + 1; j < n; j++) out.push([i, j]); return out; }
  function fromPairs(arr){ return new Set(arr.map(p => key(p[0], p[1]))); }
  function toPairs(S){ return Array.from(S).map(s => s.split(",").map(Number)).sort((p, q) => p[0] - q[0] || p[1] - q[1]); }
  function has(S, i, j){ return S.has(key(i, j)); }
  function closure(S, n){
    const C = new Set(S); let changed = true;
    while(changed){ changed = false;
      for(const [i, j] of pairs(n)) if(has(C, i, j)) for(let k = 0; k < n; k++)
        if(k !== i && k !== j && has(C, j, k) && !has(C, i, k)){ C.add(key(i, k)); changed = true; }
    }
    return C;
  }
  function isAsymmetric(S, n){ for(const [i, j] of upairs(n)) if(has(S, i, j) && has(S, j, i)) return false; for(let i = 0; i < n; i++) if(has(S, i, i)) return false; return true; }
  function isTransitive(S, n){ for(const [i, j] of pairs(n)) if(has(S, i, j)) for(let k = 0; k < n; k++) if(k !== i && k !== j && has(S, j, k) && !has(S, i, k)) return false; return true; }
  function isSpo(S, n){ return isAsymmetric(S, n) && isTransitive(S, n); }
  function isAcyclic(S, n){ return isAsymmetric(closure(S, n), n); }
  function reading(kind, n, placements, k){
    if(kind === "tier" || kind === "tier_aside"){
      const rows = {}; const S = new Set();
      for(let i = 0; i < n; i++){ const v = placements[String(i)]; rows[i] = (v === "aside") ? null : (v === undefined ? undefined : parseInt(v, 10)); }
      for(const [i, j] of pairs(n)) if(rows[i] !== null && rows[j] !== null && rows[i] !== undefined && rows[j] !== undefined && rows[i] < rows[j]) S.add(key(i, j));
      return {structure: S, coherent: true, judgments: "prec"};
    }
    if(kind === "arrow"){
      const drawn = fromPairs(placements.arrows || []);
      return {structure: closure(drawn, n), coherent: isAcyclic(drawn, n), judgments: "prec", drawn};
    }
    if(kind === "pile"){
      const S = new Set();
      for(const [i, j] of upairs(n)){ const a = placements[String(i)], b = placements[String(j)]; if(a !== undefined && b !== undefined && a === b) S.add(key(i, j)); }
      return {structure: S, coherent: true, judgments: "sim"};
    }
    if(kind === "plane"){
      const S = new Set();
      for(const [i, j] of pairs(n)){ const p = placements[String(i)], q = placements[String(j)]; if(p && q && p[0] < q[0] && p[1] < q[1]) S.add(key(i, j)); }
      return {structure: S, coherent: true, judgments: "prec"};
    }
    if(kind === "pairs"){
      const S = new Set();
      for(const [i, j] of upairs(n)){ const v = placements[key(i, j)]; if(v === "a") S.add(key(i, j)); else if(v === "b") S.add(key(j, i)); }
      return {structure: S, coherent: isSpo(S, n), judgments: "prec"};
    }
    throw new Error("unknown board kind " + kind);
  }
  function complete(kind, n, placements){
    if(kind === "arrow") return true;
    if(kind === "pairs") return upairs(n).every(([i, j]) => placements[key(i, j)] !== undefined);
    for(let i = 0; i < n; i++) if(placements[String(i)] === undefined) return false;
    return true;
  }
  function states(S, n, judgments){
    return upairs(n).map(([i, j]) => {
      let state;
      if(judgments === "sim") state = has(S, i, j) ? "tie" : "apart";
      else if(has(S, i, j)) state = "a_prec_b"; else if(has(S, j, i)) state = "b_prec_a"; else state = "apart";
      return {a: i, b: j, state};
    });
  }
  function related(S, n){ return upairs(n).filter(([i, j]) => has(S, i, j) || has(S, j, i)).length; }
  function covering(S, n){
    const out = [];
    for(const [i, j] of pairs(n)) if(has(S, i, j)){ let chain = false; for(let k = 0; k < n; k++) if(k !== i && k !== j && has(S, i, k) && has(S, k, j)) chain = true; if(!chain) out.push([i, j]); }
    return out;
  }
  function critical(S, n){
    const out = [];
    for(const [a, b] of pairs(n)){
      if(has(S, a, b) || has(S, b, a)) continue;
      const Da = [], Db = [], Ua = [], Ub = [];
      for(let x = 0; x < n; x++){ if(has(S, x, a)) Da.push(x); if(has(S, x, b)) Db.push(x); if(has(S, a, x)) Ua.push(x); if(has(S, b, x)) Ub.push(x); }
      if(Da.every(x => Db.includes(x)) && Ub.every(x => Ua.includes(x))){ const u = [Math.min(a, b), Math.max(a, b)]; if(!out.some(p => p[0] === u[0] && p[1] === u[1])) out.push(u); }
    }
    return out.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  }
  return {key, pairs, upairs, fromPairs, toPairs, has, closure, isSpo, isAcyclic, reading, complete, states, related, covering, critical};
})();
if(typeof module !== "undefined") module.exports = CardStructures;
if(typeof window !== "undefined") window.CardStructures = CardStructures;
