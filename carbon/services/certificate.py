import os
import uuid
from datetime import datetime
from django.conf import settings
from django.core.files.storage import default_storage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from ..models import CarbonOffsetPurchase, CarbonOffsetProject

class CertificateGenerator:
    """Service for generating carbon offset certificates."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_fonts()

    def _setup_fonts(self):
        """Set up custom fonts for the certificate."""
        font_path = os.path.join(settings.STATIC_ROOT, 'fonts')
        pdfmetrics.registerFont(TTFont('Roboto', os.path.join(font_path, 'Roboto-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(font_path, 'Roboto-Bold.ttf')))

    def generate_certificate(self, purchase: CarbonOffsetPurchase) -> str:
        """
        Generate a PDF certificate for a carbon offset purchase.
        
        Args:
            purchase: CarbonOffsetPurchase instance
            
        Returns:
            str: Path to the generated certificate file
        """
        # Generate unique filename
        filename = f"certificates/{uuid.uuid4()}.pdf"
        filepath = os.path.join(settings.MEDIA_ROOT, filename)
        
        # Create PDF document
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Build document content
        story = []
        
        # Add logo
        logo_path = os.path.join(settings.STATIC_ROOT, 'images', 'logo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=2*inch, height=1*inch)
            story.append(img)
            story.append(Spacer(1, 0.5*inch))

        # Add title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontName='Roboto-Bold',
            fontSize=24,
            spaceAfter=30
        )
        story.append(Paragraph("Carbon Offset Certificate", title_style))
        story.append(Spacer(1, 0.25*inch))

        # Add certificate details
        details = [
            ["Certificate ID:", purchase.certificate_id],
            ["Date Issued:", purchase.created_at.strftime("%B %d, %Y")],
            ["Project Name:", purchase.project.name],
            ["Project Type:", purchase.project.project_type],
            ["Certification Standard:", purchase.project.certification_standard],
            ["Amount Offset:", f"{purchase.amount} tons CO₂e"],
            ["Location:", f"{purchase.project.location}"],
            ["Verification Status:", purchase.verification_status]
        ]

        # Create table with details
        table = Table(details, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Roboto'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5*inch))

        # Add verification statement
        verification_style = ParagraphStyle(
            'Verification',
            parent=self.styles['Normal'],
            fontName='Roboto',
            fontSize=10,
            textColor=colors.grey
        )
        story.append(Paragraph(
            "This certificate has been verified and is registered in the Trazo Carbon Registry. "
            "The carbon offsets represented by this certificate have been retired and cannot be "
            "used for any other purpose.",
            verification_style
        ))

        # Build PDF
        doc.build(story)

        # Save file path to purchase
        purchase.certificate_file = filename
        purchase.save()

        return filename

    def verify_certificate(self, certificate_id: str) -> dict:
        """
        Verify a certificate's authenticity.
        
        Args:
            certificate_id: The certificate ID to verify
            
        Returns:
            dict: Verification details
        """
        try:
            purchase = CarbonOffsetPurchase.objects.get(certificate_id=certificate_id)
            return {
                'valid': True,
                'purchase': {
                    'id': purchase.id,
                    'amount': purchase.amount,
                    'project_name': purchase.project.name,
                    'date_issued': purchase.created_at,
                    'verification_status': purchase.verification_status
                }
            }
        except CarbonOffsetPurchase.DoesNotExist:
            return {
                'valid': False,
                'error': 'Certificate not found'
            }

# Create singleton instance
certificate_generator = CertificateGenerator() 