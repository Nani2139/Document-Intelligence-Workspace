"""
Semantic chunking service with metadata attachment.
"""
import re
from dataclasses import dataclass
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter

from backend.config import CHUNK_SIZE, CHUNK_OVERLAP
from backend.services.parsing import ParsedDocument, _table_to_markdown


@dataclass
class Chunk:
    text: str
    metadata: dict


def chunk_document(parsed_doc: ParsedDocument, document_id: int, collection_id: int) -> List[Chunk]:
    """Split a parsed document into overlapping chunks with rich metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = []
    chunk_index = 0

    for page in parsed_doc.pages:
        page_parts = [page.text]
        for table in page.tables:
            md_table = _table_to_markdown(table)
            if md_table:
                page_parts.append(md_table)

        page_text = "\n\n".join(p for p in page_parts if p.strip())
        page_text = _clean_text(page_text)

        if not page_text.strip():
            continue

        splits = splitter.split_text(page_text)

        for split_text in splits:
            has_table = "|" in split_text and "---" in split_text

            chunks.append(Chunk(
                text=split_text,
                metadata={
                    "document_id": document_id,
                    "collection_id": collection_id,
                    "filename": parsed_doc.filename,
                    "file_type": parsed_doc.file_type,
                    "page_number": page.page_number,
                    "chunk_index": chunk_index,
                    "has_table": has_table,
                    "is_ocr": page.is_ocr,
                },
            ))
            chunk_index += 1

    return chunks


def _clean_text(text: str) -> str:
    """Normalize whitespace, fix encoding artifacts, strip boilerplate."""
    text = text.replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text
