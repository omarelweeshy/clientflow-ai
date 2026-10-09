import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
workflows = list((root / "n8n").glob("*.json"))
assert len(workflows) == 5
for file in workflows:
    data = json.loads(file.read_text(encoding="utf-8"))
    names = {n["name"] for n in data["nodes"]}
    assert len(names) == len(data["nodes"])
    assert not data["active"]
    for node in data["nodes"]:
        assert "credentials" not in node
        if node["type"] == "n8n-nodes-base.httpRequest":
            assert "$env.CLIENTFLOW_API_URL" in node["parameters"]["url"]
            assert node["onError"] == "continueErrorOutput"
    for source, connection in data["connections"].items():
        assert source in names
        for output in connection["main"]:
            for target in output:
                assert target["node"] in names
    assert "sk-" not in file.read_text()
print(
    "Five exports: valid node references, error outputs and environment-only authentication."
)
