"""Resolve repository Markdown links for an embedded cloud report."""

from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit


def hosted_report(text, document, root):
    """Keep web/anchor links and map local paths to canonical GitHub main files."""
    root = Path(root).resolve()

    def replace(match):
        label, target = match.groups()
        url = urlsplit(target)
        if url.scheme or not url.path or target.startswith("//"):
            return match.group()
        destination = (Path(document).parent / unquote(url.path)).resolve()
        if not destination.is_relative_to(root) or not destination.is_file():
            raise ValueError("Report link is not a repository file")
        link = "https://github.com/ojassgambira/MMDS/blob/main/" + quote(
            destination.relative_to(root).as_posix(), safe="/"
        )
        if url.fragment:
            link += "#" + url.fragment
        return f"[{label}]({link})"

    # Figures are rendered with st.image; their relative browser URLs are invalid.
    text = "\n".join(line for line in text.splitlines() if not line.startswith("!["))
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", replace, text)
