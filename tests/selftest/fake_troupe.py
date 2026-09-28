import json, os, sys
print(json.dumps({"argv": sys.argv[1:], "actor": os.environ.get("TROUPE_ACTOR")}))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
