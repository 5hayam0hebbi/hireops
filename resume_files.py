# resume_files.py - read a resume file (PDF, Word or text) into plain text, on your computer
from io import BytesIO
from pathlib import Path

from docx import Document  # the python-docx package
from pypdf import PdfReader

KINDS = ["pdf", "docx", "txt", "md"]  # the file types the web page accepts


def read_resume(name, data):
    """Plain text of a resume. name is the file's name; data is its bytes."""
    # Path(name).suffix is the ending, like ".pdf"; .lower() makes ".PDF" work too
    kind = Path(name).suffix.lower().lstrip(".")
    # BytesIO wraps the bytes so they act like an open file
    if kind == "pdf":
        reader = PdfReader(BytesIO(data))
        # extract_text() can give None for an empty page, so "or ''" makes it ""
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if kind == "docx":
        document = Document(BytesIO(data))
        lines = [paragraph.text for paragraph in document.paragraphs]
        # Many resumes put parts in tables, so read every table cell too
        for table in document.tables:
            for row in table.rows:
                lines.extend(cell.text for cell in row.cells)
        return "\n".join(line for line in lines if line.strip())
    if kind in ("txt", "md"):
        # errors="replace" swaps any unreadable character for a ? instead of crashing
        return data.decode("utf-8", errors="replace").strip()
    raise ValueError(
        f"HireOps can't read .{kind} files. Use PDF, Word (.docx), .txt or .md."
    )