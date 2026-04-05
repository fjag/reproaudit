from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class PageText:
    document_index: int  # 0 = main paper, 1+ = supplements
    page_number: int
    text: str


def extract_pdf_text(paths: List[Path]) -> List[PageText]:
    """Extract text from one or more PDFs, preserving page numbers.

    Multiple PDFs are treated as separate documents (main + supplements).
    Uses pdfplumber as primary extractor, pypdf as fallback.
    """
    pages: List[PageText] = []
    for doc_idx, path in enumerate(paths):
        pages.extend(_extract_single(path, doc_idx))
    return pages


def _extract_single(path: Path, doc_idx: int) -> List[PageText]:
    # Try pdfplumber first (usually better text extraction)
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            result = []
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                result.append(PageText(doc_idx, i, text))
            return result
    except (OSError, IOError, ValueError, TypeError) as e:
        # Fall back to pypdf if pdfplumber fails
        pass
    except ImportError:
        pass

    # Fallback to pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        result = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            result.append(PageText(doc_idx, i, text))
        return result
    except (OSError, IOError, ValueError, TypeError) as e:
        raise RuntimeError(f"Failed to parse PDF {path}: {e}") from e
    except ImportError as e:
        raise RuntimeError(f"No PDF library available to parse {path}") from e


def pages_to_text(pages: List[PageText]) -> str:
    """Flatten pages to a single string with document/page markers."""
    chunks = []
    current_doc = -1
    for p in pages:
        if p.document_index != current_doc:
            current_doc = p.document_index
            label = "MAIN PAPER" if current_doc == 0 else f"SUPPLEMENTARY DOCUMENT {current_doc}"
            chunks.append(f"\n\n--- {label} ---\n")
        chunks.append(f"\n[Page {p.page_number}]\n{p.text}")
    return "".join(chunks)
