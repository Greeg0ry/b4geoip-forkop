from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_game_rulesets import ROOT, DownloadError, build, merge_rulesets, parse_list


class GameRulesetTests(unittest.TestCase):
    def setUp(self):
        self.enter_stdout = redirect_stdout(io.StringIO())
        self.enter_stdout.__enter__()
        self.addCleanup(self.enter_stdout.__exit__, None, None, None)

    def test_domains_and_networks_are_separate_alternatives(self):
        document = parse_list(
            "\ufeff# comment\n*.Example.COM\n.example.com\nlogin.example.com # login\n"
            "192.0.2.7\n192.0.2.42/24\n2001:db8::1\n2001:db8::ff/64\n"
        )
        self.assertEqual(document, {
            "version": 2,
            "rules": [
                {"domain_suffix": ["example.com", "login.example.com"]},
                {"ip_cidr": ["192.0.2.0/24", "192.0.2.7/32",
                             "2001:db8::/64", "2001:db8::1/128"]},
            ],
        })

    def test_invalid_or_empty_source_fails_instead_of_dropping_entries(self):
        for text in ("# empty\n", "example.com\nhttps://example.com", "192.0.2.1/99",
                     "<!DOCTYPE html>", "bad..example.com"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_list(text)

    def test_vendor_merge_retains_ip_coverage_and_removes_duplicate_networks(self):
        base = {"version": 2, "rules": [{"ip_cidr": ["192.0.2.0/24", "2001:db8::/32"]}]}
        game = parse_list("example.com\n192.0.2.0/25\n198.51.100.3\n2001:db8::1")
        self.assertEqual(merge_rulesets([base, game, game]), {
            "version": 2,
            "rules": [
                {"domain_suffix": ["example.com"]},
                {"ip_cidr": ["192.0.2.0/24", "198.51.100.3/32", "2001:db8::/32"]},
            ],
        })

    def test_vendor_merge_rejects_rules_whose_conditions_would_be_lost(self):
        with self.assertRaises(ValueError):
            merge_rulesets([{"rules": [{"port": [443], "ip_cidr": ["192.0.2.0/24"]}]}])

    def test_vendor_merge_accepts_scalar_fields_from_sing_box_decompile(self):
        document = {"rules": [{"domain_suffix": "example.com"},
                              {"domain": "exact.example.net"},
                              {"ip_cidr": "192.0.2.0/24"}]}
        self.assertEqual(merge_rulesets([document]), {
            "version": 2,
            "rules": [{"domain_suffix": ["example.com"]},
                      {"domain": ["exact.example.net"]},
                      {"ip_cidr": ["192.0.2.0/24"]}],
        })

    def test_failed_compilation_preserves_all_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "games", root / "srs"
            source.mkdir()
            output.mkdir()
            for name in ("First", "Second"):
                (source / f"{name}.txt").write_text("example.com", encoding="utf-8")
            (output / "first.srs").write_bytes(b"previous game")
            (output / "blizzard.srs").write_bytes(b"previous vendor")

            def compile_one(command, check):
                if "second.json" in command[3]:
                    raise subprocess.CalledProcessError(1, command)
                Path(command[-1]).write_bytes(b"new game")

            with patch("scripts.build_game_rulesets.subprocess.run", side_effect=compile_one):
                with self.assertRaises(subprocess.CalledProcessError):
                    build({"files": ["First.txt", "Second.txt"]}, output, "sing-box", source)
            self.assertEqual((output / "first.srs").read_bytes(), b"previous game")
            self.assertEqual((output / "blizzard.srs").read_bytes(), b"previous vendor")
            self.assertFalse((output / "second.srs").exists())

    def test_catalogue_has_23_games_without_vendor_filename_collisions(self):
        games = json.loads((ROOT / "game-sources.json").read_text(encoding="utf-8"))
        geoip = json.loads((ROOT / "srs-config.json").read_text(encoding="utf-8"))
        game_ids = [Path(name).stem.lower() for name in games["files"]]
        reserved = set(geoip["output"][0]["args"]["wantedList"]) | {"twitch", "xbox"}
        self.assertEqual(len(game_ids), 23)
        self.assertEqual(len(set(game_ids)), 23)
        self.assertFalse(set(game_ids) & reserved)
        self.assertTrue(set(games["merge"]) <= reserved)

    def test_unavailable_game_keeps_previous_and_updates_other_games(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "first.srs").write_bytes(b"previous first")
            (output / "second.srs").write_bytes(b"previous second")

            def download(url):
                if url.endswith("First.txt"):
                    raise DownloadError("source unavailable")
                return "example.com"

            def compile_one(command, check):
                Path(command[-1]).write_bytes(b"updated second")

            with patch("scripts.build_game_rulesets.fetch", side_effect=download), patch(
                "scripts.build_game_rulesets.subprocess.run", side_effect=compile_one,
            ):
                retained = build({"repository": "test/repo", "ref": "main",
                                  "files": ["First.txt", "Second.txt"]}, output, "sing-box")
            self.assertEqual(retained, ["first"])
            self.assertEqual((output / "first.srs").read_bytes(), b"previous first")
            self.assertEqual((output / "second.srs").read_bytes(), b"updated second")

    def test_unavailable_merge_restores_complete_previous_vendor_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous, output = root / "previous", root / "output"
            previous.mkdir()
            output.mkdir()
            (previous / "riot.srs").write_bytes(b"old IPs and both game domain lists")
            (output / "riot.srs").write_bytes(b"fresh GeoIP without game domains")
            with patch("scripts.build_game_rulesets.fetch", side_effect=[
                "example.com", DownloadError("second Riot source unavailable"),
            ]), patch("scripts.build_game_rulesets.subprocess.run") as compiler:
                retained = build({"repository": "test/repo", "ref": "main", "files": [],
                                  "merge": {"riot": ["First.txt", "Second.txt"]}},
                                 output, "sing-box", previous_output=previous)
            compiler.assert_not_called()
            self.assertEqual(retained, ["riot"])
            self.assertEqual((output / "riot.srs").read_bytes(),
                             (previous / "riot.srs").read_bytes())

    def test_unavailable_game_without_previous_file_fails(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.build_game_rulesets.fetch", side_effect=DownloadError("unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "no previous rule-set"):
                build({"repository": "test/repo", "ref": "main", "files": ["New.txt"]},
                      Path(temporary), "sing-box")

    def test_unavailable_geoip_skips_vendor_merge_and_keeps_complete_previous_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "riot.srs").write_bytes(b"previous complete vendor")
            with patch("scripts.build_game_rulesets.fetch") as download, patch(
                "scripts.build_game_rulesets.subprocess.run",
            ) as compiler:
                build({"repository": "test/repo", "ref": "main", "files": [],
                       "merge": {"riot": ["RiotGames_Valorant.txt"]}},
                      output, "sing-box", skip_merge=["riot"])
            download.assert_not_called()
            compiler.assert_not_called()
            self.assertEqual((output / "riot.srs").read_bytes(), b"previous complete vendor")


if __name__ == "__main__":
    unittest.main()
