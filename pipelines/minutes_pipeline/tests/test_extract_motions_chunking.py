from steps.extract_motions.chunking import (
    CHUNK_OVERLAP_CHARS,
    MAX_CHUNK_CHARS,
    split_text,
)


def _unique_text(n: int) -> str:
    """One unique Unicode character per position, so text.index(chunk) is exact."""
    return "".join(chr(0x1000 + i) for i in range(n))


def test_short_text_is_a_single_unchanged_chunk():
    assert split_text("short minutes") == ["short minutes"]


def test_exactly_max_chars_is_a_single_chunk():
    text = "a" * MAX_CHUNK_CHARS
    assert split_text(text) == [text]


def test_chunks_respect_limit_and_cover_every_character():
    text = _unique_text(200_000)
    chunks = split_text(text)
    starts = [text.index(c) for c in chunks]
    assert all(len(c) <= MAX_CHUNK_CHARS for c in chunks)
    assert starts[0] == 0
    assert starts[-1] + len(chunks[-1]) == len(text)
    for start, chunk, next_start in zip(starts, chunks, starts[1:]):
        assert next_start < start + len(chunk)          # no gap
        assert next_start >= start + len(chunk) - CHUNK_OVERLAP_CHARS  # bounded overlap


def test_prefers_a_paragraph_boundary():
    text = "A" * 70_000 + "\n\n" + "B" * 20_000
    chunks = split_text(text)
    assert len(chunks[0]) == 70_002
    assert chunks[0].endswith("\n\n")


def test_falls_back_to_a_newline_boundary():
    text = "A" * 70_000 + "\n" + "B" * 20_000
    chunks = split_text(text)
    assert len(chunks[0]) == 70_001
    assert chunks[0].endswith("\n")


def test_hard_splits_when_there_are_no_boundaries():
    text = _unique_text(200_000)
    chunks = split_text(text)
    assert [len(c) for c in chunks] == [80_000, 80_000, 48_000]


def test_a_motion_at_the_cut_point_is_fully_inside_a_later_chunk():
    sentinel = "MOTION-" + ("X" * 40)
    text = _unique_text(79_980) + sentinel + _unique_text(10_000)
    chunks = split_text(text)
    assert any(sentinel in c for c in chunks)


def test_never_returns_an_empty_chunk():
    assert all(c for c in split_text(_unique_text(200_000)))
