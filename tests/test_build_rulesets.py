from contextlib import redirect_stdout
import hashlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from scripts.build_game_rulesets import DownloadError, fetch_bytes
from scripts.build_rulesets import GEOSITE_BASE, ROOT, build, build_geoip, load_geosite


class RulesetBuildTests(unittest.TestCase):
    def setUp(self):
        self.enter_stdout = redirect_stdout(io.StringIO())
        self.enter_stdout.__enter__()
        self.addCleanup(self.enter_stdout.__exit__, None, None, None)

    def test_geosite_expands_includes_preserves_full_and_handles_tld_and_attributes(self):
        sources = {
            "xbox": "include:bethesda\ninclude:forza\ninclude:forza\nxbox\nxbox.com\nxboxlive.cn @cn",
            "bethesda": "# comment\nbethesda.net",
            "forza": "forza.net\nfull:prodforza.blob.core.windows.net",
        }
        with patch("scripts.build_rulesets.fetch", side_effect=lambda url: sources[
            url.removeprefix(GEOSITE_BASE)
        ]) as download:
            document = load_geosite("xbox")
        self.assertEqual(download.call_count, 3)
        self.assertEqual(document, {"version": 2, "rules": [
            {"domain_suffix": ["bethesda.net", "forza.net", "xbox", "xbox.com", "xboxlive.cn"]},
            {"domain": ["prodforza.blob.core.windows.net"]},
        ]})

    def test_geosite_does_not_publish_partial_includes_or_silently_drop_invalid_rules(self):
        cases = [
            (["xbox.com\ninclude:forza", DownloadError("unavailable")], DownloadError),
            (["xbox.com\ninclude:xbox"], ValueError),
            (["xbox.com\ninclude:../../other"], ValueError),
            (["xbox.com\nunknown:rule"], ValueError),
            (["<!DOCTYPE html>"], ValueError),
            (["# empty"], ValueError),
        ]
        for responses, error in cases:
            with self.subTest(responses=responses), patch(
                "scripts.build_rulesets.fetch", side_effect=responses,
            ), self.assertRaises(error):
                load_geosite("xbox")

    def test_fetch_retries_tls_http_and_incomplete_downloads(self):
        for error in (urllib.error.URLError("TLS EOF"),
                      urllib.error.HTTPError("https://example.com", 404, "missing", {}, None),
                      http.client.IncompleteRead(b"partial"), TimeoutError("timed out"),
                      ConnectionResetError("connection reset")):
            with self.subTest(error=error), patch(
                "scripts.build_game_rulesets.urllib.request.urlopen", side_effect=error,
            ) as download, patch("scripts.build_game_rulesets.time.sleep"):
                with self.assertRaises(DownloadError):
                    fetch_bytes("https://example.com/list")
                self.assertEqual(download.call_count, 3)

    def test_failed_geoip_or_checksum_download_keeps_every_existing_geoip_file(self):
        config = json.loads((ROOT / "srs-config.json").read_text())
        names = config["output"][0]["args"]["wantedList"]
        for failed_part in ("data", "checksum"):
            with self.subTest(failed_part=failed_part), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                previous, output = root / "previous", root / "output"
                previous.mkdir()
                output.mkdir()
                for name in names:
                    (previous / f"{name}.srs").write_bytes(f"old {name}".encode())
                with patch("scripts.build_rulesets.fetch_bytes", **(
                    {"side_effect": DownloadError("data unavailable")} if failed_part == "data"
                    else {"return_value": b"data"}
                )), patch("scripts.build_rulesets.fetch", side_effect=DownloadError("checksum unavailable")), patch(
                    "scripts.build_rulesets.subprocess.run",
                ) as converter:
                    retained = build_geoip(config, output, previous, root, "geoip")
                converter.assert_not_called()
                self.assertEqual(retained, names)
                for name in names:
                    self.assertEqual((output / f"{name}.srs").read_bytes(), f"old {name}".encode())

    def test_checksum_mismatch_stops_conversion(self):
        config = json.loads((ROOT / "srs-config.json").read_text())
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.build_rulesets.fetch_bytes", return_value=b"corrupt",
        ), patch("scripts.build_rulesets.fetch", return_value="0" * 64 + "  geoip.dat"), patch(
            "scripts.build_rulesets.subprocess.run",
        ) as converter:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "checksum"):
                build_geoip(config, root, root, root, "geoip")
            converter.assert_not_called()

    def test_successful_geoip_verifies_checksum_and_copies_converted_files(self):
        config = json.loads((ROOT / "srs-config.json").read_text())
        names = config["output"][0]["args"]["wantedList"]
        data = b"verified GeoIP"

        def convert(command, check):
            generated = json.loads(Path(command[-1]).read_text())
            self.assertEqual(Path(generated["input"][0]["args"]["uri"]).read_bytes(), data)
            destination = Path(generated["output"][0]["args"]["outputDir"])
            destination.mkdir()
            for name in names:
                (destination / f"{name}.srs").write_bytes(f"new {name}".encode())

        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.build_rulesets.fetch_bytes", return_value=data,
        ), patch("scripts.build_rulesets.fetch", return_value=hashlib.sha256(data).hexdigest() + "  geoip.dat"), patch(
            "scripts.build_rulesets.subprocess.run", side_effect=convert,
        ):
            root = Path(temporary)
            output = root / "output"
            output.mkdir()
            self.assertEqual(build_geoip(config, output, output, root, "geoip"), [])
            for name in names:
                self.assertEqual((output / f"{name}.srs").read_bytes(), f"new {name}".encode())

    def test_unavailable_xbox_include_keeps_binary_while_slack_twitch_and_games_update(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for name in ("xbox", "slack", "twitch", "game"):
                (output / f"{name}.srs").write_bytes(f"old {name}".encode())

            def download(url):
                if url.endswith("xbox"):
                    return "xbox.com\ninclude:forza"
                if url.endswith("forza"):
                    raise DownloadError("forza unavailable")
                return "example.com"

            def compile_one(command, check):
                Path(command[-1]).write_bytes(b"new compiled list")

            def games(config, candidates, sing_box, previous_output, skip_merge):
                (candidates / "game.srs").write_bytes(b"new game")
                return []

            with patch("scripts.build_rulesets.build_geoip", return_value=[]), patch(
                "scripts.build_rulesets.fetch", side_effect=download,
            ), patch("scripts.build_rulesets.subprocess.run", side_effect=compile_one), patch(
                "scripts.build_rulesets.build_games", side_effect=games,
            ):
                self.assertEqual(build(output), ["xbox"])
            self.assertEqual((output / "xbox.srs").read_bytes(), b"old xbox")
            for name in ("slack", "twitch"):
                self.assertEqual((output / f"{name}.srs").read_bytes(), b"new compiled list")
            self.assertEqual((output / "game.srs").read_bytes(), b"new game")

    def test_compilation_failure_leaves_original_binaries_untouched(self):
        import subprocess

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "xbox.srs").write_bytes(b"old xbox")

            def partial_compile(command, check):
                Path(command[-1]).write_bytes(b"partial broken binary")
                raise subprocess.CalledProcessError(1, command)

            with patch("scripts.build_rulesets.build_geoip", return_value=[]), patch(
                "scripts.build_rulesets.fetch", return_value="example.com",
            ), patch("scripts.build_rulesets.subprocess.run", side_effect=partial_compile):
                with self.assertRaises(subprocess.CalledProcessError):
                    build(output)
            self.assertEqual((output / "xbox.srs").read_bytes(), b"old xbox")

    def test_all_sources_unavailable_preserves_all_binaries_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "srs"
            output.mkdir()
            originals = {binary.name: binary.read_bytes() for binary in (ROOT / "srs").glob("*.srs")}
            for name, data in originals.items():
                (output / name).write_bytes(data)
            summary = root / "summary.md"
            with patch("scripts.build_rulesets.fetch_bytes", side_effect=DownloadError("offline")), patch(
                "scripts.build_rulesets.fetch", side_effect=DownloadError("offline")), patch(
                "scripts.build_game_rulesets.fetch", side_effect=DownloadError("offline")), patch(
                "scripts.build_rulesets.subprocess.run",
            ) as compiler, patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary)}):
                retained = build(output)
            compiler.assert_not_called()
            self.assertEqual(set(retained), {Path(name).stem for name in originals})
            self.assertEqual({binary.name: binary.read_bytes() for binary in output.glob("*.srs")}, originals)
            self.assertIn("xbox", summary.read_text())
            self.assertIn("riot", summary.read_text())


if __name__ == "__main__":
    unittest.main()
