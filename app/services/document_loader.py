import os

import fitz


def load_pdf(file_path: str) -> list[dict]:
    """
    Extract text from a PDF.

    Returns one dictionary per page.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    document = fitz.open(file_path)

    pages = []

    for page_number, page in enumerate(document):
        text = page.get_text("text").strip()

        if not text:
            continue

        pages.append(
            {
                "text": text,
                "page_number": page_number + 1,
                "source_file": os.path.basename(file_path),
            }
        )

    document.close()

    return pages


def load_directory(directory: str) -> list[dict]:
    """
    Load all PDFs from a directory.
    """

    if not os.path.exists(directory):
        raise FileNotFoundError(
            f"Directory not found: {directory}"
        )

    documents = []

    for filename in sorted(os.listdir(directory)):
        if not filename.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(
            directory,
            filename,
        )

        pages = load_pdf(file_path)

        documents.extend(pages)

    return documents