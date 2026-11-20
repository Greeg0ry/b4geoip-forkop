"""Build all rule-sets, retaining previous binaries for unavailable sources."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from scripts.build_game_rulesets import (
    DOMAIN, ROOT, DownloadError, build as build_games, fetch, fetch_bytes, keep_previous,
)


GEOSITE_BASE = "https://raw.githubusercontent.com/v2fly/domain-list-community/master/data/"
GEOIP_BASE = "https://github.com/DanielLavrushin/b4geoip/releases/latest/download/"
DOMAIN_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def load_geosite(name):
    """Expand upstream includes and preserve exact, suffix and regex matching."""
    matches = {key: set() for key in (
        "domain_suffix", "domain", "domain_keyword", "domain_regex",
    )}
    visited, active = set(), set()

    def load(category):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", category):
            raise ValueError(f"unsupported geosite include: {category!r}")
        if category in active:
            raise ValueError(f"cyclic geosite include: {category}")
        if category in visited:
            return
        active.add(category)
        for number, raw in enumerate(fetch(GEOSITE_BASE + category).splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            value = line.split()[0]  # @attributes are geosite metadata.
            kind, separator, content = value.partition(":")
            if separator and kind == "include":
                load(content)
                continue
            if not separator:
                kind, content = "domain", value
            key = {"domain": "domain_suffix", "full": "domain",
                   "keyword": "domain_keyword", "regexp": "domain_regex"}.get(kind)
            if key is None or not content:
                raise ValueError(f"{category}:{number}: unsupported rule: {raw!r}")
            if kind in ("domain", "full"):
                content = content.lower()
                if not (DOMAIN.fullmatch(content) or DOMAIN_LABEL.fullmatch(content)):
                    raise ValueError(f"{category}:{number}: invalid domain: {content!r}")
            matches[key].add(content)
        active.remove(category)
        visited.add(category)

    load(name)
    rules = [{key: sorted(values)} for key, values in matches.items() if values]
    if not rules:
        raise ValueError(f"{name}: geosite contains no rules")
    return {"version": 2, "rules": rules}


def build_geoip(config, output, previous_output, staging, geoip):
    names = config["output"][0]["args"]["wantedList"]
    try:
        data = fetch_bytes(GEOIP_BASE + "geoip.dat")
        checksum = fetch(GEOIP_BASE + "geoip.dat.sha256sum")
    except DownloadError as error:
        for name in names:
            keep_previous(name, previous_output, output, error)
        return list(names)

    expected = checksum.split()
    if (len(expected) != 2 or expected[1].lstrip("*") not in ("geoip.dat", "./geoip.dat")
            or hashlib.sha256(data).hexdigest() != expected[0].lower()):
        raise ValueError("geoip.dat checksum verification failed")
    source = staging / "geoip.dat"
    source.write_bytes(data)
    converted = staging / "geoip"
    config = json.loads(json.dumps(config))
    config["input"][0]["args"]["uri"] = str(source)
    config["output"][0]["args"]["outputDir"] = str(converted)
    config_path = staging / "srs-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    subprocess.run([geoip, "convert", "-c", str(config_path)], check=True)
    for name in names:
        binary = converted / f"{name}.srs"
        if not binary.is_file() or not binary.stat().st_size:
            raise ValueError(f"GeoIP conversion did not produce {name}.srs")
    for name in names:
        shutil.copyfile(converted / f"{name}.srs", output / f"{name}.srs")
    return []


def build(output, sing_box="sing-box", geoip="geoip"):
    with tempfile.TemporaryDirectory(prefix="rulesets-") as temporary:
        staging = Path(temporary)
        candidates = staging / "srs"
        shutil.copytree(output, candidates)
        config = json.loads((ROOT / "srs-config.json").read_text(encoding="utf-8"))
        retained = build_geoip(config, candidates, output, staging, geoip)
        for name in ("xbox", "slack", "twitch"):
            try:
                document = load_geosite(name)
            except DownloadError as error:
                keep_previous(name, output, candidates, error)
                retained.append(name)
                continue
            source = staging / f"{name}.json"
            source.write_text(json.dumps(document), encoding="utf-8")
            subprocess.run([sing_box, "rule-set", "compile", str(source),
                            "-o", str(candidates / f"{name}.srs")], check=True)
            print(f"{name}: compiled from v2fly/domain-list-community", flush=True)

        games = json.loads((ROOT / "game-sources.json").read_text(encoding="utf-8"))
        retained.extend(build_games(games, candidates, sing_box,
                                    previous_output=output, skip_merge=retained))
        # Original binaries are untouched until all parsing and compilation succeeds.
        for binary in sorted(candidates.glob("*.srs")):
            shutil.copyfile(binary, output / binary.name)
        if retained:
            summary = "Kept previous rule-sets (source unavailable): " + ", ".join(sorted(retained))
        else:
            summary = "All rule-set sources updated successfully."
        print(summary, flush=True)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
                handle.write(summary + "\n")
        return retained


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "srs")
    parser.add_argument("--sing-box", default="sing-box")
    parser.add_argument("--geoip", default="geoip")
    args = parser.parse_args()
    build(args.output, args.sing_box, args.geoip)


if __name__ == "__main__":
    main()
