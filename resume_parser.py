import os
from pypdf import PdfReader
from docx import Document

def extract_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if ext == ".docx":
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Only PDF and DOCX are supported.")
