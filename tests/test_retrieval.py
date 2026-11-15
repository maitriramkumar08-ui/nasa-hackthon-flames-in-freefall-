import unittest

import helpers  # noqa: F401  puts the project root on sys.path

from pyra import evidence, retrieval

PAGES = """DUMMY - NOT REAL DATA.
--- page 1 ---
# Setup
DUMMY - NOT REAL DATA. Thin paper strips burned in a small flow tunnel.

--- page 2 ---
# Results
DUMMY - NOT REAL DATA. Flame spread rate rose with air flow speed.

More results on the same page about extinction at low flow.
"""


class TestChunking(unittest.TestCase):

    def test_page_markers_and_sections(self):
        pages = retrieval.split_pages(PAGES)
        self.assertEqual([page for page, _ in pages], [None, 1, 2])
        sections = retrieval.split_sections(pages[2][1])
        self.assertEqual(sections[0][0], "Results")
        self.assertEqual(len(sections[0][1]), 2)

    def test_form_feed_pages(self):
        self.assertEqual([p for p, _ in retrieval.split_pages("one\ftwo\fthree")], [1, 2, 3])

    def test_long_text_is_cut_to_size(self):
        chunks = retrieval.pack(["word " * 1200])
        self.assertEqual([len(c.split()) for c in chunks], [500, 500, 200])

    def test_short_paragraphs_are_joined(self):
        self.assertEqual(len(retrieval.pack(["a b c", "d e f"])), 1)


class TestSearch(unittest.TestCase):

    def setUp(self):
        self.index = retrieval.Index()
        self.index.add_document("DUMMY - NOT REAL DATA. Flame spread over thin paper rose with flow speed.",
                                "dummy_a.txt", "DUMMY-A", 3, "Results")
        self.index.add_document("DUMMY - NOT REAL DATA. A heptane droplet burned on a quartz fibre.",
                                "dummy_b.txt", "DUMMY-B", 1, "Apparatus")

    def test_best_match_first_with_metadata(self):
        hits = self.index.search("heptane droplet")
        self.assertEqual(hits[0]["id"], "S2")
        self.assertEqual((hits[0]["source_id"], hits[0]["page"], hits[0]["section"]),
                         ("dummy_b.txt", 1, "Apparatus"))
        self.assertEqual(set(hits[0]), {"id", "text", "investigation", "source_id", "page", "section", "score"})

    def test_unrelated_question_gives_no_context(self):
        self.assertEqual(self.index.search("orbital mechanics of comets"), [])
        self.assertEqual(self.index.search("what is the"), [])

    def test_top_k(self):
        self.assertEqual(len(self.index.search("DUMMY flame droplet", k=1)), 1)

    def test_findings_keep_their_page(self):
        index = retrieval.Index()
        index.index_corpus(helpers.sample_corpus())
        hit = index.search("flame spread flow")[0]
        self.assertEqual((hit["investigation"], hit["page"]), ("DUMMY-A", "Figure 3"))

    def test_pdf_without_pymupdf_says_so(self):
        try:
            import fitz  # noqa: F401
            self.skipTest("PyMuPDF is installed here")
        except ImportError:
            pass
        with self.assertRaisesRegex(RuntimeError, "PyMuPDF"):
            retrieval.read_pages("paper.pdf")


class TestFiles(helpers.TempFiles, unittest.TestCase):

    def test_add_file_uses_name_and_pages(self):
        self.write("dummy_doc.md", PAGES)
        index = retrieval.index_folder(self.folder)
        hit = index.search("extinction at low flow")[0]
        self.assertEqual((hit["source_id"], hit["page"], hit["section"]), ("dummy_doc.md", 2, "Results"))


if __name__ == "__main__":
    unittest.main()
