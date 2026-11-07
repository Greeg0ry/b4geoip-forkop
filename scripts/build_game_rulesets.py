#!/usr/bin/env python3
"""Download curated game lists and compile domains and IP networks to .srs."""

import argparse
import ipaddress
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
DOMAIN = re.compile(
    r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
)


def parse_list(text):
    domains, networks = set(), set()
    for number, raw in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        value = raw.split("#", 1)[0].strip().lower()
        if not value:
            continue
        try:
            networks.add(ipaddress.ip_network(value, strict=False))
            continue
        except ValueError:
            pass
        if value.startswith("*."):
            value = value[2:]
        elif value.startswith("."):
            value = value[1:]
        if not DOMAIN.fullmatch(value):
            raise ValueError(f"line {number}: invalid domain or IP network: {raw!r}")
        domains.add(value)

    rules = []
    if domains:
        rules.append({"domain_suffix": sorted(domains)})
    if networks:
        rules.append({"ip_cidr": [str(net) for net in sorted(
            networks, key=lambda net: (net.version, int(net.network_address), net.prefixlen)
        )]})
    if not rules:
        raise ValueError("list contains no domains or IP networks")
    return {"version": 2, "rules": rules}


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "b4geoip-forkop"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8-sig")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def merge_rulesets(documents):
    """Union domain and IP matches without replacing a vendor's IP coverage."""
    def values(rule, key):
        value = rule.get(key, [])
        return [value] if isinstance(value, str) else value

    suffixes, domains, networks = set(), set(), set()
    for document in documents:
        for rule in document["rules"]:
            if set(rule) - {"domain_suffix", "domain", "ip_cidr"}:
                raise ValueError(f"cannot merge unsupported rule: {rule}")
            suffixes.update(values(rule, "domain_suffix"))
            domains.update(values(rule, "domain"))
            networks.update(ipaddress.ip_network(net) for net in values(rule, "ip_cidr"))
    rules = []
    if suffixes:
        rules.append({"domain_suffix": sorted(suffixes)})
    if domains:
        rules.append({"domain": sorted(domains)})
    if networks:
        collapsed = [str(net) for version in (4, 6) for net in ipaddress.collapse_addresses(
            net for net in networks if net.version == version
        )]
        rules.append({"ip_cidr": collapsed})
    return {"version": 2, "rules": rules}


def build(config, output, sing_box, source_dir=None):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="game-rulesets-") as temporary:
        staging = Path(temporary)

        def load(filename):
            if source_dir is None:
                url = (f"https://raw.githubusercontent.com/{config['repository']}/"
                       f"{config['ref']}/games/{filename}")
                text = fetch(url)
            else:
                text = (source_dir / filename).read_text(encoding="utf-8-sig")
            try:
                return parse_list(text)
            except ValueError as error:
                raise ValueError(f"{filename}: {error}") from error

        def compile_ruleset(name, document):
            source = staging / f"{name}.json"
            source.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            subprocess.run(
                [sing_box, "rule-set", "compile", str(source),
                 "-o", str(staging / f"{name}.srs")],
                check=True,
            )
            domains = sum(len(rule.get("domain_suffix", [])) for rule in document["rules"])
            networks = sum(len(rule.get("ip_cidr", [])) for rule in document["rules"])
            print(f"{name}: {domains} domains, {networks} networks", flush=True)

        for filename in config["files"]:
            compile_ruleset(Path(filename).stem.lower(), load(filename))

        for name, filenames in config.get("merge", {}).items():
            base = staging / f"{name}-base.json"
            subprocess.run(
                [sing_box, "rule-set", "decompile", str(output / f"{name}.srs"),
                 "-o", str(base)], check=True,
            )
            documents = [json.loads(base.read_text(encoding="utf-8"))]
            documents.extend(load(filename) for filename in filenames)
            compile_ruleset(name, merge_rulesets(documents))

        # Publish only after every input has been downloaded, parsed and compiled.
        for binary in sorted(staging.glob("*.srs")):
            shutil.copyfile(binary, output / binary.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "game-sources.json")
    parser.add_argument("--output", type=Path, default=ROOT / "srs")
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--source-dir", type=Path, help="Use already downloaded games/*.txt")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    build(config, args.output, args.sing_box, args.source_dir)


if __name__ == "__main__":
    main()
