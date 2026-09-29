from runner.egress import decisions, allowlist_text

LOG = '''Sep 28 11:41:44 [1]: Request (file descriptor 4): CONNECT api.anthropic.com:443 HTTP/1.1
Sep 28 11:41:45 [1]: Request (file descriptor 4): CONNECT example.com:443 HTTP/1.1
Sep 28 11:41:45 [1]: Proxying refused on filtered domain "example.com"
'''

def test_decisions_pair_each_connect_with_its_outcome():
    assert decisions(LOG) == [("api.anthropic.com", "allowed"), ("example.com", "refused")]

def test_allowlist_is_one_anchored_pattern_per_line():
    assert allowlist_text([r"^a\.b$", r"^c\.d$"]) == "^a\\.b$\n^c\\.d$\n"
