"""Generate credential-free n8n workflows. Business decisions stay in the API."""

import json
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1] / "n8n"
root.mkdir(exist_ok=True)


def node(name, kind, parameters, x, y, version=1):
    return {
        "id": str(uuid4()),
        "name": name,
        "type": kind,
        "typeVersion": version,
        "position": [x, y],
        "parameters": parameters,
    }


def http(name, path, method, x, y):
    result = node(
        name,
        "n8n-nodes-base.httpRequest",
        {
            "method": method,
            "url": "={{ $env.CLIENTFLOW_API_URL + '" + path + "' }}",
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "={{ 'Bearer ' + $env.AUTOMATION_SECRET }}",
                    }
                ]
            },
            "options": {"timeout": 90000},
        },
        x,
        y,
        4.2,
    )
    result["onError"] = "continueErrorOutput"
    return result


def edge(name):
    return {"node": name, "type": "main", "index": 0}


for index, (slug, title, path, method, minutes) in enumerate(
    [
        (
            "01-intake",
            "ClientFlow · Intake orchestration",
            "/automation/pending",
            "GET",
            1,
        ),
        (
            "02-crm",
            "ClientFlow · CRM synchronization",
            "/automation/crm/tick",
            "POST",
            5,
        ),
        (
            "03-email",
            "ClientFlow · Approved email delivery",
            "/automation/email/tick",
            "POST",
            1,
        ),
        (
            "04-followups",
            "ClientFlow · Follow-up stop checks",
            "/automation/followups/tick",
            "POST",
            15,
        ),
        (
            "05-failures",
            "ClientFlow · Failure notification",
            "/automation/failures/notify",
            "POST",
            5,
        ),
    ]
):
    nodes = [
        node("Manual demo run", "n8n-nodes-base.manualTrigger", {}, 0, 0),
        node(
            "Scheduled polling",
            "n8n-nodes-base.scheduleTrigger",
            {"rule": {"interval": [{"field": "minutes", "minutesInterval": minutes}]}},
            0,
            160,
            1.2,
        ),
        http("Call protected business API", path, method, 240, 0),
        node(
            "Integration error · inspect execution",
            "n8n-nodes-base.stopAndError",
            {
                "errorMessage": "ClientFlow API request failed. Inspect service health and the automation ledger before retrying."
            },
            720,
            220,
        ),
    ]
    connections = {
        "Manual demo run": {"main": [[edge("Call protected business API")]]},
        "Scheduled polling": {"main": [[edge("Call protected business API")]]},
        "Call protected business API": {
            "main": [[], [edge("Integration error · inspect execution")]]
        },
    }
    if index == 0:
        split = node(
            "One item per pending lead",
            "n8n-nodes-base.splitOut",
            {"fieldToSplitOut": "leads", "options": {}},
            480,
            0,
        )
        process = http(
            "Validate extract score and prepare draft", "PLACEHOLDER", "POST", 720, 0
        )
        process["parameters"]["url"] = (
            "={{ $env.CLIENTFLOW_API_URL + '/automation/leads/' + $json.id + '/process' }}"
        )
        nodes += [split, process]
        connections["Call protected business API"]["main"][0] = [edge(split["name"])]
        connections[split["name"]] = {"main": [[edge(process["name"])]]}
        connections[process["name"]] = {
            "main": [[], [edge("Integration error · inspect execution")]]
        }
    else:
        done = node(
            "Business outcome recorded in PostgreSQL", "n8n-nodes-base.noOp", {}, 480, 0
        )
        nodes.append(done)
        connections["Call protected business API"]["main"][0] = [edge(done["name"])]
    nodes.append(
        node(
            "Read me · no credentials in exports",
            "n8n-nodes-base.stickyNote",
            {
                "content": f"## {title}\nThe API owns state, locks, retries, consent and approval.\nSet CLIENTFLOW_API_URL and AUTOMATION_SECRET in the n8n server environment.\nManual demo run exercises the same path as scheduled polling.\nError output preserves the execution for operator review.\nHTTP 200 can contain a business failure: inspect PostgreSQL automation runs.\nNever automatically retry uncertain SMTP deliveries.",
                "height": 260,
                "width": 480,
            },
            0,
            -340,
        )
    )
    workflow = {
        "id": f"clientflow{index + 1:02d}",
        "name": title,
        "active": False,
        "nodes": nodes,
        "connections": connections,
        "settings": {
            "executionOrder": "v1",
            "saveDataErrorExecution": "all",
            "saveDataSuccessExecution": "all",
            "executionTimeout": 300,
        },
        "pinData": {},
        "versionId": str(uuid4()),
        "tags": [],
    }
    (root / f"{slug}.json").write_text(json.dumps(workflow, indent=2), encoding="utf-8")
print("Generated five n8n workflows without embedded credentials.")
