from pathlib import Path
from urllib.parse import quote, urlsplit

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx


project = "BioImageFlow Platform"
copyright = "2026, BioImageFlow Contributors"
author = "BioImageFlow Contributors"

extensions = ["myst_parser", "sphinx_reredirects"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_heading_anchors = 4
root_doc = "index"
exclude_patterns = ["_build", "build", "superpowers/**", "agents/**"]
language = "en"

redirects = {
    "user/browser-datasets": "choose-input-data.html",
    "user/installation": "index.html",
    "user/quick-start": "index.html",
}

html_theme = "furo"
html_title = "BioImageFlow Platform"
html_theme_options = {
    "source_repository": "https://github.com/Inria-SAIRPICO/bioimageflow-platform",
    "source_branch": "main",
    "source_directory": "docs/",
    "source_view_link": "https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/docs/{filename}",
    "source_edit_link": "https://github.com/Inria-SAIRPICO/bioimageflow-platform/edit/main/docs/{filename}",
}


# Campaign receipts are private local evidence, not published documentation assets.
# Their existence remains checked by scripts/verify-platform-test-links.py.
_CAMPAIGN_RECEIPTS = Path("/private/tmp/bioimageflow-library-deep-review/architecture-repair-design")
_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
_REPOSITORY_INSTRUCTIONS = {
    str(_REPOSITORY_ROOT / name.removesuffix(".md")): name
    for name in ("AGENTS.md", "PLATFORM_CONTEXT.md")
}


def _classify_campaign_links(app: Sphinx, doctree: nodes.document) -> None:
    """Separate exact filesystem/source links from ordinary MyST cross-references."""
    for node in list(doctree.findall(addnodes.pending_xref)):
        if node.get("reftype") != "myst":
            continue
        target = node.get("reftarget", "")
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or parts.query:
            continue
        path = Path(parts.path)
        if ".." in path.parts:
            continue
        uri = None
        if path.is_absolute() and path.is_relative_to(_CAMPAIGN_RECEIPTS):
            uri = path.as_uri()
        elif node.get("refdomain") == "doc" and parts.path in _REPOSITORY_INSTRUCTIONS:
            options = app.config.html_theme_options
            uri = (
                f"{options['source_repository'].rstrip('/')}/blob/"
                f"{options['source_branch']}/{_REPOSITORY_INSTRUCTIONS[parts.path]}"
            )
        if uri is None:
            continue
        fragment = node.get("reftargetid") or parts.fragment
        if fragment:
            uri += "#" + quote(fragment, safe="")
        reference = nodes.reference("", "", refuri=uri, internal=False)
        reference.source = node.source
        reference.line = node.line
        reference.extend(child.deepcopy() for child in node.children)
        node.replace_self(reference)


def setup(app: Sphinx) -> dict[str, bool]:
    app.connect("doctree-read", _classify_campaign_links)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
