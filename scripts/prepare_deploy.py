"""Write JSON extra-vars without shell quoting or Ansible key=value ambiguity."""

import argparse
import json
import re
from pathlib import Path


def deployment_vars(build_number, content_dir):
    build_number = str(build_number)
    if re.fullmatch(r"[0-9]+", build_number) is None:
        raise ValueError("Build number must contain only ASCII digits")
    content_dir = Path(content_dir).resolve()
    if not (content_dir / "index.html").is_file():
        raise ValueError(f"Missing website: {content_dir / 'index.html'}")
    return {
        "nginx_build_number": build_number,
        "nginx_content_dir": str(content_dir),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", required=True)
    parser.add_argument("--content-dir", required=True)
    parser.add_argument("--output", default="artifacts/deploy-vars.json")
    args = parser.parse_args()
    try:
        data = deployment_vars(args.build, args.content_dir)
    except ValueError as exc:
        parser.error(str(exc))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
