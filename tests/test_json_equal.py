import sys
import json

_, path1, path2 = sys.argv

with open(path1) as f, open(path2) as g:
    assert json.load(f) == json.load(g)

print("ok")
