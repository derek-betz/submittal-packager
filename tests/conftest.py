from __future__ import annotations

from pathlib import Path

import pytest
from PyPDF2 import PdfWriter
from PyPDF2.generic import DictionaryObject, NameObject, DecodedStreamObject


def create_text_pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font_dict)
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
    page[NameObject("/Resources")] = resources
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    stream = DecodedStreamObject()
    stream.set_data(content.encode("utf-8"))
    stream_ref = writer._add_object(stream)
    page[NameObject("/Contents")] = stream_ref
    with path.open("wb") as handle:
        writer.write(handle)


@pytest.fixture()
def pdf_factory(tmp_path: Path):
    def _factory(filename: str, text: str) -> Path:
        path = tmp_path / filename
        create_text_pdf(path, text)
        return path

    return _factory
