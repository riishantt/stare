from __future__ import annotations

from stare.ingest.chunker import chunk_text


def _words(n: int, tag: str = "w") -> str:
    return " ".join(f"{tag}{i}" for i in range(n))


def test_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n\n ") == []


def test_short_text_single_chunk():
    t = "One short paragraph."
    assert chunk_text(t, 350, 60) == [(0, t)]


def test_offsets_slice_original_text():
    t = "\n\n".join(f"P{i}. " + _words(40, f"p{i}_") for i in range(12))
    chunks = chunk_text(t, 100, 40)
    assert len(chunks) > 3
    for start, piece in chunks:
        assert t[start : start + len(piece)] == piece
    assert chunks[0][0] == 0
    assert [c[0] for c in chunks] == sorted(c[0] for c in chunks)


def test_paragraph_aware_and_size_limit():
    t = "\n\n".join(_words(60, f"p{i}_") for i in range(6))
    for _, piece in chunk_text(t, 130, 0):
        assert len(piece.split()) <= 130
        assert piece.startswith("p")  # chunks start on paragraph boundaries
        assert piece.count("\n\n") <= 1


def test_overlap_repeats_trailing_context():
    t = "\n\n".join(_words(20, f"p{i}_") for i in range(10))
    chunks = chunk_text(t, 70, 25)
    first_end = chunks[0][0] + len(chunks[0][1])
    assert chunks[1][0] < first_end  # second chunk starts inside the first one
    no_overlap = chunk_text(t, 70, 0)
    assert no_overlap[1][0] >= no_overlap[0][0] + len(no_overlap[0][1])


def test_oversized_paragraph_split_by_sentence_then_word():
    sentences = ". ".join(f"Sentence number {i} has some words in it" for i in range(80)) + "."
    chunks = chunk_text(sentences, 50, 5)
    assert all(len(p.split()) <= 50 for _, p in chunks)
    blob = _words(500)
    chunks = chunk_text(blob, 100, 0)
    assert len(chunks) == 5 and all(len(p.split()) == 100 for _, p in chunks)


def test_every_word_is_covered():
    t = "\n\n".join(_words(33, f"q{i}_") for i in range(9))
    covered = set()
    for _, piece in chunk_text(t, 80, 20):
        covered.update(piece.split())
    assert covered == set(t.split())
