from xhtml2pdf import pisa
from io import BytesIO

def generate_pdf(template_html):
    """
    Converts HTML string to PDF bytes in memory using xhtml2pdf (pisa).
    Returns BytesIO object containing PDF binary data, or None on error.
    """
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(template_html, dest=pdf)

    if pisa_status.err:
        return None
    return pdf
