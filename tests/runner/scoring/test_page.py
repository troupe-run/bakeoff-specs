import json, re, shutil, subprocess
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


def test_page_has_a_slider_per_dimension(p):
    s = json.loads(aggregate.run(p).read_text())
    html = page.render(p)
    # the sliders are drawn by the page script: one range input built per dimension from the embedded weights
    assert html.count("type=\"range\"") == 1 and 'min="0" max="40" step="1"' in html
    assert len(_embedded(html)["scores"]["weights"]["dimensions"]) == len(s["weights"]["dimensions"]) == 8


def test_page_meets_the_artifact_contract(p):
    aggregate.run(p)
    html = page.render(p)
    assert re.search(r"<title>[^<\s]+(?: [^<\s]+){1,3}</title>", html)
    assert ":root{--" in html and "@media (prefers-color-scheme: dark)" in html
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
    """The page's formula, in Python: dimension fraction x weight, weights renormalised to 100, None skipped."""
    s = sum(weights.values()) or 1
    return {a: sum(weights[d] / s * 100 * (x["score"] / x["max"]) for d, x in v["dimensions"].items()
                   if x["score"] is not None) for a, v in scores["arms"].items()}


def test_page_formula_at_default_weights_equals_the_scored_totals(p):
    s = json.loads(aggregate.run(p).read_text())
    got = _page_totals(s, s["weights"]["dimensions"])
    assert got.keys() == s["arms"].keys()
    for a, t in got.items():
        assert t == pytest.approx(s["arms"][a]["total"])


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_page_totals_function_run_in_node_equals_the_scored_totals(p, tmp_path):
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
