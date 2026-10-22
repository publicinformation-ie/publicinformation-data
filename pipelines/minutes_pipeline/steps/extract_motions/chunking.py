"""Split long minutes text into overlapping chunks for LLM extraction."""

MAX_CHUNK_CHARS = 80_000
CHUNK_OVERLAP_CHARS = 4_000


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS,
               overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Return overlapping chunks, each at most max_chars characters.

    Prefer a paragraph break, then a newline, in the second half of the
    candidate window; fall back to a hard cut. The next chunk starts
    `overlap` characters before the previous end, so a motion at the cut
    point is fully present in one chunk.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            floor = start + max_chars // 2  # never make a tiny first chunk
            para = text.rfind("\n\n", floor, end)
            if para != -1:
                end = min(para + 2, start + max_chars)
            else:
                line = text.rfind("\n", floor, end)
                if line != -1:
                    end = min(line + 1, start + max_chars)
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks
