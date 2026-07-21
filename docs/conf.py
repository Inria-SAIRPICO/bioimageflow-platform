project = "BioImageFlow Platform"
copyright = "2026, BioImageFlow Contributors"
author = "BioImageFlow Contributors"

extensions = ["myst_parser"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

myst_heading_anchors = 4
root_doc = "index"
exclude_patterns = ["_build", "build", "superpowers/**"]
language = "en"

html_theme = "furo"
html_title = "BioImageFlow Platform"
html_theme_options = {
    "source_repository": "https://github.com/Inria-SAIRPICO/bioimageflow-platform",
    "source_branch": "main",
    "source_directory": "docs/",
    "source_view_link": "https://github.com/Inria-SAIRPICO/bioimageflow-platform/blob/main/docs/{filename}",
    "source_edit_link": "https://github.com/Inria-SAIRPICO/bioimageflow-platform/edit/main/docs/{filename}",
}
