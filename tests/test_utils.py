# Unit tests for src/utils.py. Run: python3 -m unittest discover -s tests -v

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import utils


class CleanUrlTest(unittest.TestCase):
    def test_adds_https(self):
        self.assertEqual(utils.clean_url("example.com/a"), "https://example.com/a")

    def test_keeps_good_urls(self):
        self.assertEqual(utils.clean_url(" http://example.com "), "http://example.com")
        self.assertEqual(utils.clean_url("https://a.b/c?d=1#e"), "https://a.b/c?d=1#e")

    def test_rejects_bad_urls(self):
        bad = [None, 5, "", "   ", "ftp://x.y", "javascript:alert(1)", "https://localhost/x",
               "http://exa mple.com", "https://" + "a" * 2050 + ".com"]
        for url in bad:
            with self.subTest(url=url):
                with self.assertRaises(utils.BadUrl):
                    utils.clean_url(url)

    def test_rejects_own_host(self):
        with self.assertRaises(utils.BadUrl):
            utils.clean_url("https://my.workers.dev/abc", own_host="my.workers.dev")


class CodeAndKeyTest(unittest.TestCase):
    def test_new_code(self):
        for _ in range(200):
            code = utils.new_code()
            self.assertEqual(len(code), 6)
            self.assertTrue(utils.is_valid_code(code))
            self.assertFalse(set(code) & set("0O1lI"))

    def test_is_valid_code(self):
        self.assertTrue(utils.is_valid_code("a7Kx2"))
        for code in ["", "abc", "a/b", "../etc", "a b cd", "x" * 17]:
            self.assertFalse(utils.is_valid_code(code))

    def test_key_check(self):
        key = utils.new_key()
        key_hash = utils.hash_key(key)
        self.assertTrue(utils.check_key(key, key_hash))
        self.assertFalse(utils.check_key(key + "x", key_hash))
        self.assertFalse(utils.check_key(None, key_hash))
        self.assertFalse(utils.check_key("", key_hash))


class RefererTest(unittest.TestCase):
    def test_only_domain(self):
        self.assertEqual(utils.referer_domain("https://www.instagram.com/p/abc?x=1"), "instagram.com")
        self.assertEqual(utils.referer_domain("https://T.ME/channel"), "t.me")

    def test_empty_or_broken(self):
        self.assertIsNone(utils.referer_domain(None))
        self.assertIsNone(utils.referer_domain(""))
        self.assertIsNone(utils.referer_domain("not a url"))


class ChartTest(unittest.TestCase):
    def test_last_30_days(self):
        today = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        days = utils.last_30_days({"2026-11-20": 3, "2026-10-22": 1, "2026-01-01": 99}, today)
        self.assertEqual(len(days), 30)
        self.assertEqual(days[0], {"day": "2026-10-22", "clicks": 1})
        self.assertEqual(days[-1], {"day": "2026-11-20", "clicks": 3})
        self.assertEqual(utils.first_chart_day(today), "2026-10-22")

    def test_all_24_hours(self):
        hours = utils.all_24_hours({0: 2, 23: 1})
        self.assertEqual(len(hours), 24)
        self.assertEqual(hours[0]["clicks"], 2)
        self.assertEqual(hours[12]["clicks"], 0)

    def test_now_utc_format(self):
        self.assertRegex(utils.now_utc(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
