"""Stage: scores.json + collected records (+ optional decisions) -> report.html, one self-contained file.

The page embeds its data once (`<script type="application/json" id="data">`) and draws everything from it in
vanilla JS: no external scripts, styles or fonts. Weight sliders recompute totals with the same formula as
`confidence.total(..., "median")` (R34): 100 x the sum of each measured dimension's fraction (score / max) times its
weight, over the sum of the measured dimensions' weights; an unmeasured dimension (score None) is skipped, never
counted as 0, and an arm whose measured set differs from the field's carries † on its total."""
from __future__ import annotations
import html
import json
import re
from pathlib import Path
from runner import paths
from runner.scoring import aggregate, confidence, values

SLIDER_MAX, SLIDER_STEP = 40, 1


def _v(leaf):
    return None if leaf is None or values.is_missing(leaf) else leaf["value"]


def _time_cost(coll: dict) -> dict:
    """{arm: {step: {"seconds", "usd"}}}; a value that was not measured is null, never 0."""
    out = {}
    for arm, recs in sorted(coll.items()):
        out[arm] = {}
        for n, r in sorted(recs.items()):
            t, c = _v(r.get("time")), _v(r.get("cost"))
            out[arm][str(n)] = {"seconds": (t or {}).get("seconds") if isinstance(t, dict) else None,
                                "usd": (c or {}).get("scored_usd") if isinstance(c, dict) else None}
    return out


def _decisions(pass_: str):
    f = paths.scoring_out(pass_) / "decisions" / "ratings.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return None


def _embed(obj) -> str:
    """Every `<` becomes a JSON unicode escape, so the data can neither close the script element nor open `<!--`."""
    return json.dumps(obj, sort_keys=True).replace("<", "\\u003c")


CSS = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1d1d1b;--muted:#64625c;--card:#fff;--line:#dcd9d0;--accent:#1f5fbf;--warn:#9a5b00;--bad:#b3261e;--good:#1c7c45}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#15161a;--fg:#e8e6e1;--muted:#a09d95;--card:#1e2026;--line:#363944;--accent:#7fb0ff;--warn:#e6a94a;--bad:#ff8a80;--good:#6fd39a}}
:root[data-theme="light"]{color-scheme:light}
:root[data-theme="dark"]{color-scheme:dark;--bg:#15161a;--fg:#e8e6e1;--muted:#a09d95;--card:#1e2026;--line:#363944;--accent:#7fb0ff;--warn:#e6a94a;--bad:#ff8a80;--good:#6fd39a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.5rem 0}h2{font-size:1.2rem;margin:1.8rem 0 .5rem}h3{font-size:1rem;margin:1rem 0 .3rem}
.muted{color:var(--muted)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:.6rem 0}
.scroll{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
details{margin:.3rem 0}summary{cursor:pointer}
.sliders{display:grid;grid-template-columns:1fr;gap:.5rem}
.sl{display:grid;grid-template-columns:1fr auto;gap:.2rem .6rem;align-items:center}
.sl input{grid-column:1/3;width:100%}
.notice{border-left:4px solid var(--warn);padding:.3rem .6rem;margin:.5rem 0}
button{font:inherit;padding:.3rem .8rem;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
ol.rank{padding-left:1.4rem;margin:.3rem 0}
@media (min-width:600px){.sliders{grid-template-columns:1fr 1fr}}
"""

JS = r"""
const data = JSON.parse(document.getElementById('data').textContent);
const DASH = '—';
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function num(x, d) { return x === null || x === undefined ? DASH : Number(x).toFixed(d === undefined ? 1 : d); }
function mins(s) { return s === null || s === undefined ? DASH : (s / 60).toFixed(1) + ' min'; }
function usd(x) { return x === null || x === undefined ? DASH : '$' + Number(x).toFixed(2); }
function fraction(dim) { return dim.score === null ? null : dim.score / dim.max; }
function totals(weights) {
  // R34: renormalised over the weight of the measured dimensions; an unmeasured one is skipped, never a 0.
  const out = {};
  for (const [arm, v] of Object.entries(data.scores.arms)) {
    let num = 0, den = 0;
    for (const [d, dim] of Object.entries(v.dimensions)) {
      const f = fraction(dim); if (f !== null) { num += weights[d] * f; den += weights[d]; }
    }
    out[arm] = den > 0 ? 100 * num / den : null;
  }
  return out;
}
function partial(arm) { return !!data.scores.arms[arm].total_partial; }
const PARTIAL = 'total renormalised over its measured dimensions: not like-for-like with the field';
function unmeasured(arm) {
  return Object.entries(data.scores.arms[arm].dimensions).filter(([d, x]) => x.score === null || x.unmeasured_parts.length).map(([d]) => d);
}
function key(x) { return x === null ? -Infinity : x; }
function order(t) { return Object.keys(t).sort((a, b) => (key(t[b]) - key(t[a])) || (a < b ? -1 : 1)); }
const base = Object.assign({}, data.scores.weights.dimensions);
let current = Object.assign({}, base);
const baseTotals = totals(base), baseOrder = data.confidence.ranking;
const TOL = 1e-9;
function orderChanged(t) {
  for (let i = 0; i < baseOrder.length; i++) for (let j = i + 1; j < baseOrder.length; j++)
    if (t[baseOrder[i]] !== null && t[baseOrder[j]] !== null && t[baseOrder[i]] - t[baseOrder[j]] < -TOL) return true;
  return false;
}
function renderRanking() {
  const t = totals(current), arms = order(t);
  const changed = orderChanged(t);
  let h = '<ol class="rank">' + arms.map(a => '<li><b>' + esc(a) + '</b> ' + num(t[a]) +
    (partial(a) ? '<span class="warn" title="' + PARTIAL + '">†</span>' : '') +
    (t[a] !== null && baseTotals[a] !== null && Math.abs(t[a] - baseTotals[a]) > TOL ? ' <span class="muted">(base ' + baseTotals[a].toFixed(1) + ')</span>' : '') +
    (unmeasured(a).length ? ' <span class="muted" title="unmeasured: ' + esc(unmeasured(a).join(', ')) + '">(unmeasured: ' + esc(unmeasured(a).join(', ')) + ')</span>' : '') + '</li>').join('') + '</ol>';
  if (changed) h += '<div class="notice" role="status">Order changed: the ranking with these weights differs from the base order (' + baseOrder.map(esc).join(' > ') + ').</div>';
  document.getElementById('ranking').innerHTML = h;
}
function renderGroups() {
  const c = data.confidence, s = data.scores;
  const gs = c.groups.filter(g => g.length > 1);
  let h = '<p>' + (gs.length ? gs.length + ' group(s) of arms are within noise of each other and should not be ranked against one another: ' +
    gs.map(g => g.map(esc).join(' · ')).join('; ') + '.' : 'The order is settled for every arm.') + ' ' +
    c.order_changes.length + ' weight/judge variant(s) change the order.</p>';
  h += '<div class="scroll"><table><tr><th>arm</th><th>reported</th><th>lowest</th><th>highest</th></tr>' +
    c.ranking.map(a => '<tr><td>' + esc(a) + '</td><td>' + num(s.arms[a].total) + (partial(a) ? '†' : '') + '</td><td>' + num(c.intervals[a][0]) + '</td><td>' + num(c.intervals[a][1]) + '</td></tr>').join('') + '</table></div>';
  if (c.order_changes.length) h += '<details><summary>Variants that change the order</summary><ul>' +
    c.order_changes.map(o => '<li>' + esc(o.variant) + ': ' + o.order.map(esc).join(' > ') + '</li>').join('') + '</ul></details>';
  document.getElementById('confidence').innerHTML = h;
}
function renderSliders() {
  const el = document.getElementById('sliders');
  el.innerHTML = Object.keys(base).map(d => '<div class="sl"><label for="w-' + esc(d) + '">' + esc(d) + '</label><output id="o-' + esc(d) + '">' + base[d] + '</output>' +
    '<input type="range" id="w-' + esc(d) + '" data-dim="' + esc(d) + '" min="0" max="__SMAX__" step="__SSTEP__" value="' + base[d] + '"></div>').join('');
  el.querySelectorAll('input').forEach(i => i.addEventListener('input', () => {
    current[i.dataset.dim] = Number(i.value);
    document.getElementById('o-' + i.dataset.dim).textContent = i.value;
    renderRanking(); renderScorecard();
  }));
  document.getElementById('reset').addEventListener('click', () => {
    current = Object.assign({}, base);
    el.querySelectorAll('input').forEach(i => { i.value = base[i.dataset.dim]; document.getElementById('o-' + i.dataset.dim).textContent = i.value; });
    renderRanking(); renderScorecard();
  });
}
function renderScorecard() {
  const arms = data.scores.arms, dims = Object.keys(base), t = totals(current);
  const names = order(t);
  document.getElementById('scorecard').innerHTML = '<table><tr><th>arm</th>' + dims.map(d => '<th>' + esc(d) + ' /' + base[d] + '</th>').join('') + '<th>total /100</th></tr>' +
    names.map(a => '<tr><td>' + esc(a) + '</td>' + dims.map(d => { const x = arms[a].dimensions[d];
      return '<td>' + num(x.score) + (x.score === null || x.unmeasured_parts.length ? '<span class="warn">†</span>' : '') + '</td>'; }).join('') +
      '<td><b>' + num(t[a]) + (partial(a) ? '†' : '') + '</b></td></tr>').join('') + '</table>';
}
function stepCells(st) {
  if (!st) return DASH;
  return num(st.score, 2) + (st.disputed ? '*' : '') + (st.owner !== undefined ? '°' : '') + (st.thin ? '◦' : '') + (st.why ? ' <span class="muted">' + esc(st.why) + '</span>' : '');
}
function renderDimensions() {
  const arms = Object.keys(data.scores.arms).sort(), w = data.scores.weights;
  document.getElementById('dimensions').innerHTML = Object.keys(w.dimensions).map(d => {
    const parts = Object.keys(data.scores.arms[arms[0]].dimensions[d].parts);
    return '<details><summary>' + esc(d) + ' (/' + w.dimensions[d] + ')</summary><div class="scroll"><table><tr><th>part</th>' + arms.map(a => '<th>' + esc(a) + '</th>').join('') + '</tr>' +
      parts.map(p => {
        const keys = new Set(); arms.forEach(a => Object.keys(data.scores.arms[a].dimensions[d].parts[p].steps).forEach(k => keys.add(k)));
        const ks = Array.from(keys).sort((x, y) => (/^\d+$/.test(x) ? 0 : 1) - (/^\d+$/.test(y) ? 0 : 1) || (/^\d+$/.test(x) ? x - y : (x < y ? -1 : 1)));
        return '<tr><th>' + esc(p) + '</th>' + arms.map(a => '<td>' + num(data.scores.arms[a].dimensions[d].parts[p].score, 2) + '</td>').join('') + '</tr>' +
          ks.map(k => '<tr><td class="muted">&nbsp;&nbsp;' + (k === 'arm' ? 'arm' : 'step ' + esc(k)) + '</td>' +
            arms.map(a => '<td>' + stepCells(data.scores.arms[a].dimensions[d].parts[p].steps[k]) + '</td>').join('') + '</tr>').join('');
      }).join('') + '</table></div><p class="muted">Part scores are 0–1. * judges disagreed by 2+ points; ° owner verdict used; ◦ thin panel (fewer than three lenses answered); ' + DASH + ' unmeasured or not applicable.</p></details>';
  }).join('');
}
function renderTimeCost() {
  const tc = data.time_cost, arms = Object.keys(tc).sort();
  const steps = Array.from(new Set(arms.flatMap(a => Object.keys(tc[a])))).sort((x, y) => x - y);
  document.getElementById('timecost').innerHTML = steps.map(n => '<details><summary>Step ' + esc(n) + '</summary><div class="scroll"><table><tr><th>arm</th><th>time</th><th>cost (scored)</th></tr>' +
    arms.map(a => { const r = tc[a][n]; return '<tr><td>' + esc(a) + '</td><td>' + mins(r && r.seconds) + '</td><td>' + usd(r && r.usd) + '</td></tr>'; }).join('') + '</table></div></details>').join('') || '<p class="muted">No time or cost recorded.</p>';
}
function renderDecisions() {
  const d = data.decisions;
  if (!d || !d.topics) { document.getElementById('decisions-sec').hidden = true; return; }
  document.getElementById('decisions').innerHTML = d.topics.map(t => '<details><summary>' + esc(t.question || t.id || '?') + '</summary><ul>' +
    t.routes.map(r => '<li>' + esc(r.route || '?') + ' [' + r.arms.map(esc).join(', ') + ']: ' + esc(r.rating === undefined ? DASH : r.rating) + (r.reason ? ' — ' + esc(r.reason) : '') + '</li>').join('') + '</ul></details>').join('');
}
renderSliders(); renderRanking(); renderScorecard(); renderGroups(); renderDimensions(); renderTimeCost(); renderDecisions();
if (typeof module !== 'undefined') module.exports = { totals };
""".replace("__SMAX__", str(SLIDER_MAX)).replace("__SSTEP__", str(SLIDER_STEP))

HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bake-off scorecard</title>
<style>__CSS__</style></head>
<body><main>
<h1>Bake-off scorecard</h1><p class="muted">Pass __PASS__. Move the sliders to try other weights; totals and ranking update live.</p>
<h2>Bottom line</h2><div class="card" id="ranking"></div><div class="card" id="confidence"></div>
<h2>Weights</h2><div class="card"><div class="sliders" id="sliders"></div><p><button id="reset" type="button">Reset to base weights</button></p>
<p class="muted">Each total is renormalised over the weight of the dimensions that arm had measured: a dimension with no measurement is skipped, never counted as 0. † on a total: that arm's measured dimensions differ from the field's, so its total is not like-for-like.</p></div>
<h2>Scorecard</h2><div class="card scroll" id="scorecard"></div>
<h2>Dimensions</h2><div id="dimensions"></div>
<section id="decisions-sec"><h2>Decision review</h2><div id="decisions"></div></section>
<h2>Time and cost</h2><div id="timecost"></div>
<h2>Flags</h2><ul>__FLAGS__</ul>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>__JS__</script>
</body></html>
"""


def render(pass_: str) -> str:
    scores = json.loads((paths.scoring_out(pass_) / "scores.json").read_text())
    conf = confidence.check(scores)
    data = {"scores": scores, "confidence": conf, "time_cost": _time_cost(aggregate.collected(pass_)),
            "decisions": _decisions(pass_)}
    flags = "".join(f"<li>{html.escape(f)}</li>" for f in scores["flags"]) or "<li>None.</li>"
    subs = {"__CSS__": CSS, "__PASS__": html.escape(pass_), "__FLAGS__": flags, "__DATA__": _embed(data), "__JS__": JS}
    return re.sub("__(?:CSS|PASS|FLAGS|DATA|JS)__", lambda m: subs[m.group(0)], HTML)  # one pass: values are never re-scanned


def run(pass_: str) -> Path:
    out = paths.scoring_out(pass_) / "report.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(pass_))
    return out
