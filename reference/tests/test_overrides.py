"""Step 5 overrides at the Config level (the reference runs as step 7 by default, so overrides are on)."""
from troupe_ref.config import Config


def test_deep_new_key_inside_an_included_list_item_goes_to_the_file_holding_the_list(tmp_path):
    (tmp_path / "troupe.yml").write_text("c: file:c.yaml\n")
    (tmp_path / "c.yaml").write_text("tools:\n  - model: a\n  - model: b\n")
    cfg = Config(tmp_path / "troupe.yml")
    cfg.set("c.tools.0.sub.name", "val")
    assert (tmp_path / "c.yaml").read_text() == "tools:\n  - model: a\n    sub:\n      name: val\n  - model: b\n"
    assert (tmp_path / "troupe.yml").read_text() == "c: file:c.yaml\n"
    assert cfg.get("c.tools") == [{"model": "a", "sub": {"name": "val"}}, {"model": "b"}]
