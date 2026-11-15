"""Check how often search finds the right page for a set of hand-written questions.

    python tools/eval_retrieval.py                 DUMMY questions and docs, k = 6
    python tools/eval_retrieval.py -k 3 --questions my.json --docs papers/

Each question lists the pages that should come back, as "file name#page".
recall@k is the share of those pages found in the top k results, averaged
over the questions. The bundled set is DUMMY, so its score only shows the
pipeline runs; real numbers need real questions about real papers.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pyra import retrieval  # noqa: E402

EVAL = ROOT / "data" / "eval"


def recall_at_k(index, questions, k):
    """(average recall, [questions with at least one expected page missing])."""
    total, missed = 0.0, []
    for entry in questions:
        found = {f"{hit['source_id']}#{hit['page']}" for hit in index.search(entry["question"], k)}
        expected = set(entry["expected"])
        total += len(expected & found) / len(expected)
        if expected - found:
            missed.append((entry["question"], sorted(expected - found)))
    return total / len(questions), missed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report recall@k for the retrieval index.")
    parser.add_argument("-k", type=int, default=retrieval.TOP_K)
    parser.add_argument("--questions", default=EVAL / "dummy_questions.json")
    parser.add_argument("--docs", default=EVAL / "docs")
    args = parser.parse_args(argv)

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))["questions"]
    index = retrieval.index_folder(args.docs)
    recall, missed = recall_at_k(index, questions, args.k)
    for question, pages in missed:
        print(f"missed {', '.join(pages)} for: {question}")
    print(f"recall@{args.k} = {recall:.2f} over {len(questions)} questions ({len(index.chunks)} chunks)")


if __name__ == "__main__":
    main()
