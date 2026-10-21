"""
Load the versioned corpus: Markdown with front matter.

The Week-3 loader reads PDFs and derives what metadata it can
from the filename and the text. That was enough while every
policy had exactly one edition and applied to everyone.

It is not enough now. Three facts decide whether an answer is
right, and none of them can be read reliably out of prose:

    version + effective_date   which edition was in force
    entity                     which law applies to this person
    overrides                  which document wins a conflict

So the Week-12 documents declare them in front matter, and this
loader lifts them onto every chunk. A filter on a declared
field is enforceable; a date mentioned inside a paragraph is
only a string that might rank well.

PDFs still load through `document_loader.py`. This is an
addition, not a replacement - the handbook did not move.
"""

import os
import re


FRONT_MATTER = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)

# A heading starts a section. The level does not matter; what
# matters is that a chunk never spans two of them, because a
# citation has to point at one clause.
HEADING = re.compile(
    r"^(#{1,6})\s+(.*)$",
    re.MULTILINE,
)

# "## A2.1 Annual Leave" -> "A2.1", "## 3.1 Parental" -> "3.1"
SECTION_NUMBER = re.compile(
    r"^([A-Z]?\d+(?:\.\d+)*)\s+"
)


def parse_front_matter(
    text: str,
) -> tuple[dict, str]:
    """
    Returns (fields, body).

    Deliberately not YAML: the fields here are flat strings,
    and a hand-rolled parser keeps the ingest path free of a
    dependency whose failure mode is a silent type change.
    """

    match = FRONT_MATTER.match(text)

    if not match:
        return {}, text

    fields = {}

    for line in match.group(1).split("\n"):

        if ":" not in line:
            continue

        key, _, value = line.partition(":")

        value = value.strip().strip('"').strip("'")

        fields[key.strip()] = value

    return fields, text[match.end() :]


def split_sections(body: str) -> list[dict]:
    """
    One chunk per heading, carrying its own heading text.
    """

    matches = list(HEADING.finditer(body))

    if not matches:

        return [
            {
                "heading": "",
                "section": "",
                "text": body.strip(),
            }
        ]

    sections = []

    for index, match in enumerate(matches):

        start = match.end()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(body)
        )

        heading = match.group(2).strip()

        content = body[start:end].strip()

        if not content:
            continue

        number = SECTION_NUMBER.match(heading)

        # A document's title heading is a preamble, not a
        # clause: it carries the version banner and a note on
        # why the edition is retained. It indexes well on
        # words like "entitled" and "2024" and then gets cited
        # as though it stated an entitlement, which is a
        # citation to nothing. Only numbered sections are
        # clauses, so the rest is skipped.
        if number is None:
            continue

        sections.append(
            {
                "heading": heading,
                "section": number.group(1),
                # The heading is kept in the text so a
                # retrieved chunk reads as a clause rather
                # than as an orphaned paragraph, and so the
                # section number is searchable.
                "text": f"{heading}\n{content}",
            }
        )

    return sections


def load_markdown(file_path: str) -> list[dict]:

    with open(
        file_path,
        "r",
        encoding="utf-8",
    ) as file:

        raw = file.read()

    fields, body = parse_front_matter(raw)

    source_file = os.path.basename(file_path)

    chunks = []

    for section in split_sections(body):

        chunks.append(
            {
                "text": section["text"],
                "source_file": source_file,
                "page_number": 0,
                # The three fields that decide correctness.
                "policy_id": fields.get(
                    "policy_id",
                    "",
                ),
                "version": fields.get(
                    "version",
                    "",
                ),
                "effective_date": fields.get(
                    "effective_date",
                    "unknown",
                ),
                "superseded_on": fields.get(
                    "superseded_on",
                    "",
                ),
                "entity": fields.get(
                    "entity",
                    "GLOBAL",
                ),
                "overrides": fields.get(
                    "overrides",
                    "",
                ),
                "title": fields.get("title", ""),
                "section": section["section"],
                "heading": section["heading"],
            }
        )

    return chunks


def load_markdown_directories(
    directories: list[str],
) -> list[dict]:
    """
    Every .md under each directory that exists.

    A missing directory is skipped rather than raised: the
    corpus is assembled from several places and an absent one
    is a smaller corpus, not a broken ingest.
    """

    documents = []

    for directory in directories:

        if not os.path.isdir(directory):
            continue

        for filename in sorted(
            os.listdir(directory)
        ):

            if not filename.lower().endswith(
                ".md"
            ):
                continue

            documents.extend(
                load_markdown(
                    os.path.join(
                        directory,
                        filename,
                    )
                )
            )

    return documents
