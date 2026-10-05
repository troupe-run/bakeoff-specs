import json, re, shutil, subprocess, textwrap
import pytest
from runner.scoring import aggregate, page
from tests.runner.scoring.test_aggregate import p  # noqa: F401


def _embedded(html):
    return json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)[1])


def test_page_embeds_exactly_the_scores_it_was_built_from(p):
    s = json.loads(aggregate.run(p).read_text())
    assert _embedded(page.render(p))["scores"] == s


def test_page_loads_nothing_from_outside(p):
    aggregate.run(p)
    html = page.render(p)
    assert not re.search(r'(src|href)="https?://', html)
    assert not re.search(r'<script[^>]*\ssrc=|<link\b|@import|url\(', html)


def test_page_template_has_the_slider_markup_and_data_carries_eight_weights(p):
    # Python-side only: the range inputs are drawn by the page script (see the node tests for them being drawn).
    aggregate.run(p)
    html = page.render(p)
    assert 'type="range"' in html and 'min="0" max="40" step="1"' in html
    assert len(_embedded(html)["scores"]["weights"]["dimensions"]) == 8


def test_page_meets_the_artifact_contract(p):
    aggregate.run(p)
    html = page.render(p)
    assert re.search(r"<title>[^<\s]+(?: [^<\s]+){1,3}</title>", html)
    assert "--bg:" in html and "color-scheme:light dark" in html and "@media (prefers-color-scheme: dark)" in html
    assert ':root:not([data-theme="light"])' in html and ':root[data-theme="dark"]' in html
    assert re.search(r"body\{[^}]*background:var\(--bg\)", html)
    assert 'name="viewport"' in html and "overflow-x:auto" in html


def test_embedded_json_cannot_close_the_script_element(p):
    aggregate.run(p)
    html = page.render(p)
    body = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)[1]
    assert "</" not in body


def test_flag_text_is_html_escaped(p):
    s = json.loads(aggregate.run(p).read_text())
    s["flags"] = ["<img src=x onerror=alert(1)> & co"]
    (aggregate.paths.scoring_out(p) / "scores.json").write_text(json.dumps(s))
    html = page.render(p)
    html = re.sub(r'<script type="application/json" id="data">.*?</script>', "", html, flags=re.S)  # data is inert
    assert "<img src=x" not in html and "&lt;img src=x onerror=alert(1)&gt; &amp; co" in html


def _page_totals(scores, weights):
    """The page's formula, in Python (R34): dimension fraction x weight over the weight of the measured dimensions
    only, x 100; an unmeasured dimension is skipped, never a 0. None when no measured dimension has weight."""
    out = {}
    for a, v in scores["arms"].items():
        m = {d: x["score"] / x["max"] for d, x in v["dimensions"].items() if x["score"] is not None}
        den = sum(weights[d] for d in m)
        out[a] = 100 * sum(weights[d] * f for d, f in m.items()) / den if den > 0 else None
    return out


def test_page_formula_at_default_weights_equals_the_scored_totals(p):
    s = json.loads(aggregate.run(p).read_text())
    got = _page_totals(s, s["weights"]["dimensions"])
    assert got.keys() == s["arms"].keys()
    for a, t in got.items():
        assert t == pytest.approx(s["arms"][a]["total"])


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")

HARNESS = textwrap.dedent("""
    const job = JSON.parse(require('fs').readFileSync(0, 'utf8'));
    const els = {};
    function mk(id) {
      const o = {id, textContent: '', innerHTML: '', hidden: false, handlers: {}, inputs: {},
        addEventListener(t, h) { this.handlers[t] = h; },
        querySelectorAll() {
          if (id !== 'sliders') return [];
          const out = [], re = /<input [^>]*data-dim="([^"]*)"[^>]*value="([^"]*)"/g; let m;
          while ((m = re.exec(this.innerHTML))) {
            const i = this.inputs[m[1]] || (this.inputs[m[1]] = {dataset: {dim: m[1]}, handlers: {},
              addEventListener(t, h) { this.handlers[t] = h; }});
            i.value = m[2]; out.push(i);
          }
          return out;
        }};
      return o;
    }
    const el = id => els[id] || (els[id] = mk(id));
    global.document = {getElementById: id => { const e = el(id); if (id === 'data') e.textContent = job.dataText; return e; }};
    const m = {exports: {}};
    (new Function('module', 'document', job.script))(m, global.document);
    const snap = () => Object.fromEntries(Object.entries(els).map(([k, v]) => [k, v.innerHTML]));
    const out = {load: snap(), sliders: Object.entries(el('sliders').inputs).map(([k, i]) => ({dim: k, value: i.value})),
                 steps: []};
    for (const a of job.actions) {
      if (a.slide) { const i = el('sliders').inputs[a.slide[0]]; i.value = String(a.slide[1]); i.handlers.input(); }
      if (a.reset) el('reset').handlers.click();
      out.steps.push(el('ranking').innerHTML);
    }
    console.log(JSON.stringify(out));
""")


def _run_page(html, actions=(), data_text=None):
    script = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    if data_text is None:
        data_text = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)[1]
    job = {"script": script, "dataText": data_text, "actions": list(actions)}
    r = subprocess.run(["node", "-e", HARNESS], input=json.dumps(job), capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


@needs_node
def test_page_script_draws_one_range_slider_per_dimension(p):
    s = json.loads(aggregate.run(p).read_text())
    out = _run_page(page.render(p))
    sliders = out["load"]["sliders"]
    dims = list(s["weights"]["dimensions"])
    assert sliders.count('type="range"') == len(dims) == 8
    assert re.findall(r'data-dim="([^"]*)"', sliders) == dims
    assert sliders.count('min="0" max="40" step="1"') == 8


@needs_node
def test_page_totals_function_equals_the_scored_totals(p, tmp_path):
    s = json.loads(aggregate.run(p).read_text())
    html = page.render(p)
    script = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    harness = tmp_path / "h.js"
    harness.write_text(
        "const data=%s;\n"
        "const el=()=>({textContent:'',innerHTML:'',hidden:false,addEventListener(){},querySelectorAll(){return []}});\n"
        "global.document={getElementById:id=>id==='data'?{textContent:JSON.stringify(data)}:el()};\n"
        "const m={exports:{}};global.module=m;\n"
        "(new Function('module','document',%s))(m,global.document);\n"
        "const w=m.exports.totals;\n"
        "const d=data.scores.weights.dimensions;\n"
        "const alt=Object.assign({},d);const k=Object.keys(d)[0];alt[k]=0;\n"
        "console.log(JSON.stringify({base:w(d),alt:w(alt)}));\n" % (json.dumps(_embedded(html)), json.dumps(script)))
    out = json.loads(subprocess.run(["node", str(harness)], capture_output=True, text=True, check=True).stdout)
    for a, t in out["base"].items():
        assert t == pytest.approx(s["arms"][a]["total"])
    alt = dict(s["weights"]["dimensions"]); alt[next(iter(alt))] = 0
    for a, t in out["alt"].items():
        assert t == pytest.approx(_page_totals(s, alt)[a])


HOSTILE = '<img src=x onerror=alert(1)> & "q" \'q\' </script><!--<script>'


@needs_node
def test_hostile_strings_reach_the_drawn_html_only_in_escaped_form(p):
    s = json.loads(aggregate.run(p).read_text())
    s["arms"][HOSTILE] = s["arms"].pop("alpha")
    dim = next(iter(s["arms"]["control"]["dimensions"]))
    part = next(iter(s["arms"]["control"]["dimensions"][dim]["parts"]))
    s["arms"]["control"]["dimensions"][dim]["parts"][part]["steps"]["1"] = {"score": None, "why": HOSTILE}
    s["arms"][HOSTILE]["dimensions"][dim]["unmeasured_parts"] = [HOSTILE]
    s["flags"] = [HOSTILE]
    out_dir = aggregate.paths.scoring_out(p)
    (out_dir / "scores.json").write_text(json.dumps(s))
    (out_dir / "decisions").mkdir()
    (out_dir / "decisions" / "ratings.json").write_text(json.dumps({"topics": [
        {"id": HOSTILE, "question": HOSTILE, "routes": [{"route": HOSTILE, "arms": [HOSTILE], "rating": HOSTILE}]}]}))
    html = page.render(p)
    out = _run_page(html)
    drawn = "\n".join(out["load"][k] for k in out["load"] if k != "data")
    assert "&lt;img src=x onerror=alert(1)&gt;" in drawn and "&lt;/script&gt;" in drawn
    assert "<img" not in drawn and "</script" not in drawn and "<!--" not in drawn
    for k in ("ranking", "confidence", "scorecard", "dimensions", "decisions"):
        assert HOSTILE not in out["load"][k], k
    # and the page as a whole still has exactly the data script and the code script
    assert len(re.findall(r"<script", html)) == 2


def test_embedded_json_cannot_open_a_comment_either(p):
    s = json.loads(aggregate.run(p).read_text())
    s["arms"]["<!--<script>"] = s["arms"].pop("alpha")
    (aggregate.paths.scoring_out(p) / "scores.json").write_text(json.dumps(s))
    html = page.render(p)
    body = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)[1]
    assert "<" not in body and _embedded(html)["scores"]["arms"]["<!--<script>"]


def test_run_writes_report_html_and_a_rerun_is_byte_identical(p):
    aggregate.run(p)
    out = page.run(p)
    assert out.name == "report.html" and out.parent == aggregate.paths.scoring_out(p)
    first = out.read_bytes()
    assert first.startswith(b"<!doctype html>")
    assert page.run(p).read_bytes() == first


def test_a_percent_sign_in_data_or_flags_survives_templating(p):
    s = json.loads(aggregate.run(p).read_text())
    s["flags"] = ["100% %(css)s __JS__"]
    (aggregate.paths.scoring_out(p) / "scores.json").write_text(json.dumps(s))
    html = page.render(p)
    assert "<li>100% %(css)s __JS__</li>" in html


def _two_arm_data(order=("A", "B")):
    def dim(score, mx):
        return {"score": score, "max": mx, "unmeasured_parts": [], "parts": {}}
    arms = {"A": {"total": 66.7, "dimensions": {"d1": dim(20, 20), "d2": dim(0, 10)}},
            "B": {"total": 33.3, "dimensions": {"d1": dim(0, 20), "d2": dim(10, 10)}}}
    return {"scores": {"baseline": "A", "weights": {"dimensions": {"d1": 20, "d2": 10}, "parts": {}}, "arms": arms,
                       "flags": []},
            "confidence": {"ranking": list(order), "intervals": {"A": [60, 70], "B": [30, 40]},
                           "groups": [["A"], ["B"]], "order_changes": []},
            "time_cost": {}, "decisions": None}


@needs_node
def test_order_changed_notice_appears_when_a_slider_flips_the_order_and_reset_clears_it(p):
    aggregate.run(p)
    html = page.render(p)
    out = _run_page(html, actions=[{"slide": ["d1", 0]}, {"reset": True}], data_text=json.dumps(_two_arm_data()))
    assert "Order changed" not in out["load"]["ranking"]
    assert out["steps"][0].index("<b>B</b>") < out["steps"][0].index("<b>A</b>") and "Order changed" in out["steps"][0]
    assert "Order changed" not in out["steps"][1] and out["steps"][1].index("<b>A</b>") < out["steps"][1].index("<b>B</b>")


def _probe_data():
    """R34 probe: X 45/50 on d1, d2 unmeasured; Y 30/50 on both. X 90 > Y 60; X's total is partial."""
    def dim(score, mx):
        return {"score": score, "max": mx, "unmeasured_parts": [] if score is not None else ["p"], "parts": {}}
    arms = {"X": {"total": 90.0, "total_partial": True, "dimensions": {"d1": dim(45, 50), "d2": dim(None, 50)}},
            "Y": {"total": 60.0, "total_partial": False, "dimensions": {"d1": dim(30, 50), "d2": dim(30, 50)}}}
    return {"scores": {"baseline": "Y", "weights": {"dimensions": {"d1": 50, "d2": 50}, "parts": {}}, "arms": arms,
                       "flags": []},
            "confidence": {"ranking": ["X", "Y"], "intervals": {"X": [90, 90], "Y": [60, 60]},
                           "groups": [["X"], ["Y"]], "order_changes": []},
            "time_cost": {}, "decisions": None}


@needs_node
def test_page_totals_are_renormalised_and_a_partial_total_carries_a_dagger_on_ranking_and_scorecard(p):
    aggregate.run(p)
    out = _run_page(page.render(p), actions=[{"slide": ["d2", 10]}], data_text=json.dumps(_probe_data()))
    ranking, card = out["load"]["ranking"], out["load"]["scorecard"]
    assert "<b>X</b> 90.0" in ranking and "<b>Y</b> 60.0" in ranking
    assert ranking.index("<b>X</b>") < ranking.index("<b>Y</b>")
    x_line = ranking[ranking.index("<b>X</b>"):ranking.index("<b>Y</b>")]
    assert "†" in x_line and "†" not in ranking[ranking.index("<b>Y</b>"):]
    x_row = card[card.index("<td>X</td>"):card.index("<td>Y</td>")]
    assert "<b>90.0†</b>" in x_row
    # moving d2's weight (unmeasured for X) leaves X's renormalised total where it was
    assert "<b>X</b> 90.0" in out["steps"][0]


@needs_node
def test_the_page_marks_a_thin_panel_in_the_dimension_detail(p):
    write_judged = __import__("tests.runner.scoring.test_aggregate", fromlist=["x"]).write_judged
    write_collected = __import__("tests.runner.scoring.test_aggregate", fromlist=["x"]).write_collected
    write_collected(p, "alpha", 3)
    write_judged(p, "req_test_code", "alpha", "03", [2, 3])
    aggregate.run(p)
    dims = _run_page(page.render(p))["load"]["dimensions"]
    assert re.search(r"0\.6[23]◦", dims) and "thin panel" in dims          # JS rounds 0.625 up
