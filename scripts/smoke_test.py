"""Fail unless every nginx inventory host serves the expected build at /build."""

import argparse
import http.client
import json
import re
import sys
import time
from pathlib import Path


def inventory_targets(inventory):
    """Use ansible-inventory --list JSON so inventory and smoke hosts cannot drift."""
    if "nginx" not in inventory:
        raise ValueError("Inventory has no nginx group")
    seen = set()
    hosts = set()

    def visit(group_name):
        if group_name in seen:
            return
        seen.add(group_name)
        group = inventory.get(group_name, {})
        hosts.update(group.get("hosts", []))
        for child in group.get("children", []):
            visit(child)

    visit("nginx")
    if not hosts:
        raise ValueError("The nginx inventory group is empty")
    hostvars = inventory.get("_meta", {}).get("hostvars", {})
    targets = []
    for name in sorted(hosts):
        variables = hostvars.get(name, {})
        host = str(variables.get("ansible_host", name))
        if not host or any(char.isspace() or char in "/?#@[]" for char in host):
            raise ValueError(f"Invalid HTTP host for {name}: {host!r}")
        port = int(variables.get("nginx_http_port", 8080))
        if not 1 <= port <= 65535:
            raise ValueError(f"Invalid HTTP port for {name}: {port}")
        targets.append((name, host, port))
    return targets


def fetch_build(host, port, timeout):
    # Direct connections ignore HTTP proxy environment variables and redirects.
    connection = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        connection.request("GET", "/build", headers={"Cache-Control": "no-cache"})
        response = connection.getresponse()
        body = response.read(1024).decode("utf-8").strip()
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        return body
    finally:
        connection.close()


def check_targets(targets, expected_build, attempts=5, delay=2, timeout=5,
                  fetch=fetch_build, sleep=time.sleep):
    if not targets:
        raise ValueError("Refusing to pass a smoke test with zero targets")
    if attempts < 1 or delay < 0 or timeout <= 0:
        raise ValueError("Attempts/timeout must be positive; delay must be nonnegative")
    expected_build = str(expected_build)
    if re.fullmatch(r"[0-9]+", expected_build) is None:
        raise ValueError("Expected build must contain only ASCII digits")
    results = []
    for name, host, port in targets:
        error = ""
        for attempt in range(attempts):
            try:
                actual = fetch(host, port, timeout)
                if actual == expected_build:
                    error = ""
                    break
                error = f"expected {expected_build!r}, received {actual!r}"
            except (OSError, ValueError, http.client.HTTPException) as exc:
                error = str(exc) or type(exc).__name__
            if attempt + 1 < attempts:
                sleep(delay)
        results.append({"name": name, "host": host, "port": port,
                        "passed": not error, "error": error})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="ansible-inventory --list JSON")
    parser.add_argument("--expected-build", required=True)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--report", default="artifacts/smoke.json")
    args = parser.parse_args()
    try:
        inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
        results = check_targets(
            inventory_targets(inventory), args.expected_build,
            args.attempts, args.delay, args.timeout,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Smoke test configuration error: {exc}", file=sys.stderr)
        return 2
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"expected_build": args.expected_build,
                                  "results": results}, indent=2) + "\n", encoding="utf-8")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['name']} ({result['host']}:{result['port']}) {result['error']}")
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
