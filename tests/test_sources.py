import unittest

from helpers import TempFiles

from phase0.sources import check_sources

HEADER = "id,investigation,url,access_date,verified_by\n"


class TestSources(TempFiles, unittest.TestCase):

    def test_missing_verifier_is_flagged(self):
        f = self.write("s.csv", HEADER + "S01,BASS-II,https://example.org,2026-11-14,\n")
        problems = check_sources(f)
        self.assertEqual(len(problems), 1)
        self.assertIn("verified_by", problems[0])

    def test_complete_row_passes(self):
        f = self.write("s.csv", HEADER + "S01,BASS-II,https://example.org,2026-11-14,Asha\n")
        self.assertEqual(check_sources(f), [])

    def test_lists_every_missing_field(self):
        f = self.write("s.csv", HEADER + "S02,SAME,,,\n")
        self.assertEqual(check_sources(f),
                         ["S02 (SAME): missing url, access_date, verified_by"])


if __name__ == "__main__":
    unittest.main()
