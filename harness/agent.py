"""Acme Outfitters support agent harness.

The harness is generic: model, prompt, tools and limits all come from the agent
bundle that the Kargo promotion uploads to /sandbox/agent. Prompt, tool and
model changes ship without rebuilding this image. Where the Orders API is
depends on the stage, so the platform sets it as ORDERS_API_URL when it creates
the sandbox.

Usage (inside an OpenShell sandbox, via `openshell sandbox exec`):
  python3 /app/agent.py chat --customer C-1001 "Where is my order A-5002?"
  python3 /app/agent.py probe POST http://orders-api.orders.svc.cluster.local/orders/A-5001/refunds \
      --body '{"amount": 1, "reason": "policy probe"}'

Both commands print a single JSON object on stdout, which the eval runner reads.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

import anthropic
import yaml

BUNDLE_DIR = os.environ.get("AGENT_BUNDLE_DIR", "/sandbox/agent")


def load_bundle(path):
    with open(os.path.join(path, "agent.yaml")) as f:
        config = yaml.safe_load(f)
    with open(os.path.join(path, "system-prompt.md")) as f:
        prompt = f.read()
    with open(os.path.join(path, "tools.yaml")) as f:
        tools = yaml.safe_load(f)["tools"]
    return config, prompt, tools


def http_request(method, url, body=None):
    """Make an HTTP request through the sandbox's egress proxy.

    OpenShell sets the proxy environment variables, and urllib picks them up.
    Returns (status, parsed_body). Denied requests come back as HTTP errors.
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, {"error": text[:500]}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def run_tool(tool, tool_input, base_url):
    spec = tool["http"]
    params = dict(tool_input)
    path = spec["path"]
    for key in list(params):
        placeholder = "{" + key + "}"
        if placeholder in path:
            path = path.replace(placeholder, str(params.pop(key)))
    body = params if spec["method"] != "GET" else None
    return http_request(spec["method"], base_url + path, body)


def chat(customer_id, message):
    orders_api_url = os.environ.get("ORDERS_API_URL")
    if not orders_api_url:
        sys.exit("ORDERS_API_URL is not set")
    config, prompt, tools = load_bundle(BUNDLE_DIR)
    tools_by_name = {t["name"]: t for t in tools}
    model = config["model"]
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY is an OpenShell placeholder

    messages = [{"role": "user", "content": message}]
    trace = []
    reply = ""
    stop_reason = None
    for _ in range(config.get("max_turns", 6)):
        response = client.beta.messages.create(
            model=model["id"],
            max_tokens=model.get("max_tokens", 16000),
            output_config={"effort": model.get("effort", "low")},
            system=prompt.replace("{customer_id}", customer_id),
            tools=[{k: t[k] for k in ("name", "description", "input_schema")} for t in tools],
            messages=messages,
            # If a safety classifier declines, the API retries on Anthropic's
            # recommended fallback model instead of returning a refusal.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        stop_reason = response.stop_reason
        # Append the full content (not just text) so the history stays append-only.
        messages.append({"role": "assistant", "content": response.content})
        reply = "".join(b.text for b in response.content if b.type == "text")
        if stop_reason != "tool_use":
            break

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            status, result = run_tool(tools_by_name[block.name], block.input, orders_api_url)
            trace.append({"tool": block.name, "input": block.input, "status": status})
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
                "is_error": not 200 <= status < 300,
            })
        messages.append({"role": "user", "content": results})

    return {"model": model["id"], "stop_reason": stop_reason, "reply": reply, "tool_calls": trace}


def probe(method, url, body=None):
    status, response = http_request(method, url, json.loads(body) if body else None)
    return {"method": method, "url": url, "status": status, "body": response}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("chat")
    c.add_argument("--customer", required=True)
    c.add_argument("message")
    p = sub.add_parser("probe")
    p.add_argument("method")
    p.add_argument("url")
    p.add_argument("--body", help="JSON request body. Use a valid one, so an allowed request succeeds.")
    args = parser.parse_args()

    if args.command == "chat":
        result = chat(args.customer, args.message)
    else:
        result = probe(args.method.upper(), args.url, args.body)
    json.dump(result, sys.stdout)
    print()


if __name__ == "__main__":
    main()
