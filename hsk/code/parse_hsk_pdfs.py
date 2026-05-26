"""
Parse HSK vocabulary PDFs and produce cumulative word lists.
Each level's JSON contains all words from HSK 1 through that level.
Strategy: vocabulary words sit at x=50 in the PDF; example sentences are indented.
"""

import json
import re
import pdfplumber
from pathlib import Path

PDF_DIR = Path(__file__).parent.parent / "pdf"
JSON_DIR = Path(__file__).parent.parent / "json"

CHINESE_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
VOCAB_X = 50.0
X_TOLERANCE = 5.0

EXPECTED = {1: 300, 2: 496, 3: 988, 4: 1978, 5: 3557, 6: 5334, 7: 10896}


def extract_words_from_pdf(pdf_path: Path) -> list[str]:
    words, seen = [], set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for w in page.extract_words():
                if abs(w["x0"] - VOCAB_X) <= X_TOLERANCE and CHINESE_ONLY.match(w["text"]):
                    word = w["text"]
                    if word not in seen:
                        seen.add(word)
                        words.append(word)
    return words


def main():
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    all_ok = True
    cumulative: list[str] = []
    seen_all: set[str] = set()

    for level in range(1, 8):
        pdf_path = PDF_DIR / f"hsk-{level}-vocabulary.pdf"
        for w in extract_words_from_pdf(pdf_path):
            if w not in seen_all:
                seen_all.add(w)
                cumulative.append(w)

        snapshot = list(cumulative)
        out_path = JSON_DIR / f"hsk{level}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        expected = EXPECTED[level]
        ok = len(snapshot) == expected
        if not ok:
            all_ok = False
        status = "OK" if ok else f"MISMATCH (expected {expected})"
        print(f"HSK {level}: {len(snapshot)} cumulative words -> {out_path.name} [{status}]")

    print("\nAll counts match." if all_ok else "\nSome counts do not match - review above.")


if __name__ == "__main__":
    main()