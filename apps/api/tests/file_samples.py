from io import BytesIO

from pypdf import PdfWriter


def make_pdf_bytes(*, password: str | None = None) -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if password is not None:
        writer.encrypt(password)
    writer.write(stream)
    return stream.getvalue()
