"""
Document Generator for Rice Export FSMS

Generates standardized document cover pages and headers according to
ISO 22001:2018 requirements. Updates PDFs with proper document control
information before moving to controlled folder.
"""

import os
from datetime import datetime
from pathlib import Path
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter


# ============================================================================
# Configuration
# ============================================================================

# Company branding colors
PRIMARY_COLOR = HexColor("#1a5276")  # Dark blue
SECONDARY_COLOR = HexColor("#2980b9")  # Light blue
ACCENT_COLOR = HexColor("#27ae60")  # Green for approved
WARNING_COLOR = HexColor("#e74c3c")  # Red for draft

# Document control watermark
WATERMARK_CONTROLLED = "CONTROLLED COPY"
WATERMARK_DRAFT = "DRAFT - UNCONTROLLED"


# ============================================================================
# Cover Page Generation
# ============================================================================

def create_cover_page(document: dict, output_path: str) -> str:
    """
    Create a standardized cover page PDF for a document.

    Args:
        document: Document data dictionary from API
        output_path: Path to save the cover page PDF

    Returns:
        Path to the created cover page PDF
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=PRIMARY_COLOR,
        alignment=TA_CENTER,
        spaceAfter=30
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=SECONDARY_COLOR,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=PRIMARY_COLOR,
        spaceBefore=15,
        spaceAfter=5
    )

    normal_style = ParagraphStyle(
        'NormalCenter',
        parent=styles['Normal'],
        alignment=TA_CENTER
    )

    # Build the cover page content
    story = []

    # Company Header
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("RICE EXPORT FSMS", title_style))
    story.append(Paragraph("Food Safety Management System", subtitle_style))
    story.append(Paragraph("ISO 22001:2018 Compliant", normal_style))
    story.append(Spacer(1, 1*cm))

    # Document Title
    story.append(Paragraph(f"<b>{document.get('title', 'Untitled Document')}</b>", title_style))
    story.append(Spacer(1, 0.5*cm))

    # Document ID and Version Box
    doc_id = document.get('doc_id', 'N/A')
    version = document.get('version', 'v0.1')
    status = document.get('status', 'Draft')

    status_color = ACCENT_COLOR if status == "Controlled" else WARNING_COLOR

    id_table_data = [
        ['Document ID', doc_id],
        ['Version', version],
        ['Status', status],
        ['Department', document.get('department', 'N/A')]
    ]

    id_table = Table(id_table_data, colWidths=[4*cm, 8*cm])
    id_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (0, -1), white),
        ('BACKGROUND', (1, 2), (1, 2), status_color),
        ('TEXTCOLOR', (1, 2), (1, 2), white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, black),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 1*cm))

    # Ownership Section
    story.append(Paragraph("DOCUMENT OWNERSHIP", header_style))

    ownership_data = [
        ['Prepared By:', document.get('prepared_by', 'Not Assigned')],
        ['Approved By:', document.get('approved_by', 'Not Assigned')],
        ['Record Keeper:', document.get('record_keeper', 'Not Assigned')],
    ]

    ownership_table = Table(ownership_data, colWidths=[4*cm, 10*cm])
    ownership_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor("#ecf0f1")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#bdc3c7")),
    ]))
    story.append(ownership_table)
    story.append(Spacer(1, 0.5*cm))

    # Dates Section
    story.append(Paragraph("DOCUMENT CONTROL DATES", header_style))

    approval_date = document.get('approval_date', '')
    if approval_date:
        if isinstance(approval_date, str):
            approval_date = approval_date[:10]  # Get just the date part
    else:
        approval_date = 'Pending'

    review_months = document.get('review_cycle_months', 12)

    dates_data = [
        ['Effective Date:', approval_date],
        ['Review Cycle:', f'{review_months} months'],
        ['Created:', document.get('created_at', 'N/A')[:10] if document.get('created_at') else 'N/A'],
    ]

    dates_table = Table(dates_data, colWidths=[4*cm, 10*cm])
    dates_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor("#ecf0f1")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#bdc3c7")),
    ]))
    story.append(dates_table)
    story.append(Spacer(1, 0.5*cm))

    # ISO Clauses Section
    iso_clauses = document.get('iso_clauses', '')
    if iso_clauses:
        story.append(Paragraph("APPLICABLE ISO 22001:2018 CLAUSES", header_style))
        story.append(Paragraph(iso_clauses, styles['Normal']))
        story.append(Spacer(1, 0.5*cm))

    # Document Control Notice
    story.append(Spacer(1, 1*cm))

    if status == "Controlled":
        notice_text = """
        <b>CONTROLLED DOCUMENT</b><br/><br/>
        This is a controlled copy of an approved document. The master copy is maintained in the
        Document Control system. Any printed copies are uncontrolled unless stamped 'CONTROLLED COPY'.
        <br/><br/>
        Unauthorized copying, distribution, or modification of this document is prohibited.
        """
        notice_bg = ACCENT_COLOR
    else:
        notice_text = """
        <b>DRAFT DOCUMENT - NOT FOR OPERATIONAL USE</b><br/><br/>
        This document is in draft status and has not been approved for use.
        Do not use this document for operational purposes until it has been approved
        and marked as 'Controlled'.
        """
        notice_bg = WARNING_COLOR

    notice_style = ParagraphStyle(
        'Notice',
        parent=styles['Normal'],
        fontSize=9,
        textColor=white,
        alignment=TA_CENTER,
        backColor=notice_bg,
        borderPadding=10
    )

    notice_table = Table([[Paragraph(notice_text, notice_style)]], colWidths=[14*cm])
    notice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), notice_bg),
        ('PADDING', (0, 0), (-1, -1), 15),
    ]))
    story.append(notice_table)

    # Footer with hash
    story.append(Spacer(1, 1*cm))
    file_hash = document.get('file_hash', '')
    if file_hash:
        hash_text = f"Document Hash: {file_hash[:32]}..."
        story.append(Paragraph(hash_text, ParagraphStyle('Hash', fontSize=8, textColor=HexColor("#7f8c8d"))))

    # Build the PDF
    doc.build(story)

    return output_path


def add_header_footer(input_pdf: str, output_pdf: str, document: dict):
    """
    Add header and footer to each page of an existing PDF.

    Args:
        input_pdf: Path to input PDF
        output_pdf: Path to output PDF
        document: Document data dictionary
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    doc_id = document.get('doc_id', 'N/A')
    version = document.get('version', 'v0.1')
    status = document.get('status', 'Draft')

    for page_num, page in enumerate(reader.pages, 1):
        # Create overlay with header/footer
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        width, height = A4

        # Header
        can.setFont("Helvetica-Bold", 8)
        can.setFillColor(PRIMARY_COLOR)
        can.drawString(2*cm, height - 1*cm, f"{doc_id} | {version}")
        can.drawRightString(width - 2*cm, height - 1*cm, document.get('title', '')[:50])

        # Header line
        can.setStrokeColor(PRIMARY_COLOR)
        can.line(2*cm, height - 1.2*cm, width - 2*cm, height - 1.2*cm)

        # Footer
        can.setFont("Helvetica", 8)
        can.setFillColor(HexColor("#7f8c8d"))
        can.drawString(2*cm, 1*cm, f"Status: {status}")
        can.drawCentredString(width/2, 1*cm, f"Page {page_num} of {len(reader.pages)}")
        can.drawRightString(width - 2*cm, 1*cm, "Rice Export FSMS")

        # Footer line
        can.line(2*cm, 1.3*cm, width - 2*cm, 1.3*cm)

        # Watermark for controlled documents
        if status == "Controlled":
            can.setFont("Helvetica-Bold", 8)
            can.setFillColor(ACCENT_COLOR)
            can.drawString(2*cm, 0.5*cm, "CONTROLLED COPY")

        can.save()

        # Move to the beginning of the BytesIO buffer
        packet.seek(0)

        # Read the overlay
        overlay = PdfReader(packet)

        # Merge overlay with original page
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    # Write the output
    with open(output_pdf, 'wb') as output_file:
        writer.write(output_file)


def generate_controlled_document(
    source_pdf: str,
    document: dict,
    output_folder: str = "documents/controlled"
) -> str:
    """
    Generate a complete controlled document with cover page and headers.

    Args:
        source_pdf: Path to the original PDF
        document: Document data dictionary from API
        output_folder: Output folder for controlled document

    Returns:
        Path to the generated controlled document
    """
    from doc_controller import generate_controlled_filename, sanitize_filename

    Path(output_folder).mkdir(parents=True, exist_ok=True)

    doc_id = document.get('doc_id', 'FSMS-DOC-000')
    version = document.get('version', 'v1.0')
    title = document.get('title', 'Untitled')

    # Generate output filename
    sanitized_title = sanitize_filename(title)
    output_filename = f"{doc_id}_{version}_{sanitized_title}.pdf"
    output_path = str(Path(output_folder) / output_filename)

    # Step 1: Create cover page
    cover_page_path = f"/tmp/cover_{doc_id}.pdf"
    create_cover_page(document, cover_page_path)

    # Step 2: Add headers/footers to original content
    content_with_headers_path = f"/tmp/content_{doc_id}.pdf"
    add_header_footer(source_pdf, content_with_headers_path, document)

    # Step 3: Merge cover page with content
    writer = PdfWriter()

    # Add cover page
    cover_reader = PdfReader(cover_page_path)
    for page in cover_reader.pages:
        writer.add_page(page)

    # Add content pages with headers/footers
    content_reader = PdfReader(content_with_headers_path)
    for page in content_reader.pages:
        writer.add_page(page)

    # Write final document
    with open(output_path, 'wb') as output_file:
        writer.write(output_file)

    # Cleanup temp files
    try:
        os.remove(cover_page_path)
        os.remove(content_with_headers_path)
    except:
        pass

    return output_path


def update_draft_document(source_pdf: str, document: dict) -> str:
    """
    Update a draft document with current metadata (for preview before approval).
    Saves to the same location with _PREVIEW suffix.

    Args:
        source_pdf: Path to the original PDF
        document: Document data dictionary

    Returns:
        Path to the preview document
    """
    output_path = source_pdf.replace('.pdf', '_PREVIEW.pdf')

    # Just add headers/footers without cover page for drafts
    add_header_footer(source_pdf, output_path, document)

    return output_path


# ============================================================================
# Utility Functions
# ============================================================================

def get_document_info_text(document: dict) -> str:
    """
    Generate a text summary of document info for embedding.

    Args:
        document: Document data dictionary

    Returns:
        Formatted text string
    """
    return f"""
Document ID: {document.get('doc_id', 'N/A')}
Title: {document.get('title', 'N/A')}
Version: {document.get('version', 'N/A')}
Status: {document.get('status', 'N/A')}
Department: {document.get('department', 'N/A')}

Prepared By: {document.get('prepared_by', 'Not Assigned')}
Approved By: {document.get('approved_by', 'Not Assigned')}
Record Keeper: {document.get('record_keeper', 'Not Assigned')}

Effective Date: {document.get('approval_date', 'Pending')[:10] if document.get('approval_date') else 'Pending'}
Review Cycle: {document.get('review_cycle_months', 12)} months
"""
