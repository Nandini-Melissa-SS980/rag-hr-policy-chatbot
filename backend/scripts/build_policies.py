"""
Render the policy PDFs from their Markdown source.

    python -m scripts.build_policies

The PDFs in documents/addenda/ are what the app ingests, but
a PDF is a bad place to keep text you want to edit: you
cannot diff it, and a change leaves no reviewable trace.

So the text lives in documents/source/*.md and this renders
it. Editing a policy means editing the Markdown and running
this, which means every wording change shows up in a diff.

Layout matches the header block the original PDFs used, so
`extract_policy_id` and `extract_section` keep working
unchanged and the Week-4 retrieval numbers stay comparable.
"""

import os
import re

import pymupdf

from app.config import ADDENDA_DIR, DOCUMENTS_DIR


SOURCE_DIR = os.path.join(
    DOCUMENTS_DIR,
    "source",
)

# A4 at 72dpi, with the margins the original PDFs used.
PAGE_WIDTH = 595

PAGE_HEIGHT = 842

MARGIN = 56

BODY_WIDTH = PAGE_WIDTH - MARGIN * 2

FRONT_MATTER = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)

HEADING = re.compile(r"^(#{1,3})\s+(.*)$")


def parse_source(text: str) -> tuple[dict, str]:

    match = FRONT_MATTER.match(text)

    if not match:
        return {}, text

    fields = {}

    for line in match.group(1).split("\n"):

        if ":" not in line:
            continue

        key, _, value = line.partition(":")

        fields[key.strip()] = (
            value.strip().strip('"').strip("'")
        )

    return fields, text[match.end() :]


class Writer:
    """
    A cursor that lays out text and breaks pages itself.
    """

    def __init__(self):

        self.document = pymupdf.open()

        self.page = None

        self.y = 0.0

        self.new_page()

    def new_page(self):

        self.page = self.document.new_page(
            width=PAGE_WIDTH,
            height=PAGE_HEIGHT,
        )

        self.y = MARGIN

    def space(self, amount: float):

        self.y += amount

    def write(
        self,
        text: str,
        size: float = 10.0,
        font: str = "helv",
        leading: float = 1.35,
        gap_after: float = 6.0,
    ):
        """
        One paragraph, wrapped, breaking the page when it
        runs out of room.
        """

        line_height = size * leading

        # Measured rather than guessed, so a long word does
        # not silently overflow the margin.
        words = text.split()

        line = ""

        lines = []

        for word in words:

            candidate = (
                f"{line} {word}".strip()
            )

            width = pymupdf.get_text_length(
                candidate,
                fontname=font,
                fontsize=size,
            )

            if width > BODY_WIDTH and line:
                lines.append(line)
                line = word

            else:
                line = candidate

        if line:
            lines.append(line)

        for one in lines:

            if (
                self.y + line_height
                > PAGE_HEIGHT - MARGIN
            ):
                self.new_page()

            self.page.insert_text(
                (MARGIN, self.y + size),
                one,
                fontname=font,
                fontsize=size,
            )

            self.y += line_height

        self.y += gap_after

    def rule(self):

        if self.y + 12 > PAGE_HEIGHT - MARGIN:
            self.new_page()

        self.page.draw_line(
            (MARGIN, self.y),
            (PAGE_WIDTH - MARGIN, self.y),
            color=(0.72, 0.72, 0.75),
            width=0.6,
        )

        self.y += 10


def render(
    fields: dict,
    body: str,
) -> pymupdf.Document:

    writer = Writer()

    # Title
    writer.write(
        f"{fields['policy_id']} {fields['title']}",
        size=16,
        font="hebo",
        gap_after=10,
    )

    # The header block, in the same shape the original PDFs
    # used: two labelled lines plus the applies-to line.
    writer.write(
        f"Policy ID: {fields['policy_id']}   "
        f"Version: {fields['version']}   "
        f"Classification: {fields['classification']}",
        size=9,
        gap_after=2,
    )

    writer.write(
        f"Effective Date: {fields['effective_date']}"
        f"   Owner: {fields['owner']}",
        size=9,
        gap_after=2,
    )

    writer.write(
        f"Applies to: {fields['applies_to']}",
        size=9,
        gap_after=8,
    )

    writer.rule()

    for block in body.split("\n\n"):

        block = block.strip()

        if not block:
            continue

        heading = HEADING.match(block)

        if heading:

            level = len(heading.group(1))

            writer.write(
                heading.group(2),
                size=13 if level == 1 else 11,
                font="hebo",
                gap_after=4,
            )

            continue

        writer.write(
            " ".join(block.split()),
            size=10,
        )

    return writer.document


def main():

    if not os.path.isdir(SOURCE_DIR):

        raise SystemExit(
            f"No source directory at {SOURCE_DIR}."
        )

    os.makedirs(ADDENDA_DIR, exist_ok=True)

    built = 0

    for filename in sorted(
        os.listdir(SOURCE_DIR)
    ):

        if not filename.endswith(".md"):
            continue

        with open(
            os.path.join(SOURCE_DIR, filename),
            "r",
            encoding="utf-8",
        ) as handle:

            fields, body = parse_source(
                handle.read()
            )

        if not fields.get("policy_id"):

            print(
                f"  skipped {filename}: no "
                "policy_id in front matter"
            )

            continue

        document = render(fields, body)

        target = os.path.join(
            ADDENDA_DIR,
            f"{fields['policy_id']}.pdf",
        )

        document.save(target)

        print(
            f"  {fields['policy_id']:8} "
            f"{document.page_count}pp  "
            f"{fields['title']}"
        )

        document.close()

        built += 1

    print(
        f"\nBuilt {built} PDFs into {ADDENDA_DIR}."
    )

    print(
        "Re-index with: python -m scripts.ingest"
    )


if __name__ == "__main__":
    main()
