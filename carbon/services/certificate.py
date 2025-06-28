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
from .verification import verification_service

class CertificateGenerator:
    """Service for generating carbon offset certificates with blockchain verification."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.production_mode = getattr(settings, 'DEBUG', True) == False
        self.require_blockchain_verification = self.production_mode or getattr(settings, 'FORCE_BLOCKCHAIN_VERIFICATION', False)
        self._setup_fonts()

    def _setup_fonts(self):
        """Set up custom fonts for the certificate."""
        font_path = os.path.join(settings.STATIC_ROOT, 'fonts')
        pdfmetrics.registerFont(TTFont('Roboto', os.path.join(font_path, 'Roboto-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(font_path, 'Roboto-Bold.ttf')))

    def generate_certificate(self, purchase: CarbonOffsetPurchase) -> str:
        """
        Generate a PDF certificate for a carbon offset purchase.
        REQUIRES BLOCKCHAIN VERIFICATION in production.
        
        Args:
            purchase: CarbonOffsetPurchase instance
            
        Returns:
            str: Path to the generated certificate file
            
        Raises:
            ValueError: If blockchain verification is required but not available
        """
        # CRITICAL: Verify blockchain verification before generating certificate
        if self.require_blockchain_verification:
            verification_result = verification_service.verify_purchase(purchase)
            
            # Check if blockchain verification passed
            blockchain_check = verification_result.get('checks', {}).get('blockchain', {})
            if not blockchain_check.get('passed', False):
                error_msg = (
                    f"Certificate generation failed: Blockchain verification required but not passed. "
                    f"Details: {blockchain_check.get('details', 'Unknown error')}"
                )
                raise ValueError(error_msg)
            
            # Log successful verification for audit trail
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Certificate generated for purchase {purchase.id} with blockchain verification")
        else:
            # Development mode warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Certificate generated for purchase {purchase.id} WITHOUT blockchain verification (development mode)")
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

        # Add blockchain verification status to certificate
        blockchain_status = "BLOCKCHAIN VERIFIED" if self.require_blockchain_verification else "DEVELOPMENT MODE"
        
        # Add certificate details
        details = [
            ["Certificate ID:", purchase.certificate_id],
            ["Date Issued:", purchase.created_at.strftime("%B %d, %Y")],
            ["Project Name:", purchase.project.name],
            ["Project Type:", purchase.project.project_type],
            ["Certification Standard:", purchase.project.certification_standard],
            ["Amount Offset:", f"{purchase.amount} tons CO₂e"],
            ["Location:", f"{purchase.project.location}"],
            ["Verification Status:", purchase.verification_status],
            ["Blockchain Status:", blockchain_status]
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
        verification_text = (
            "This certificate has been verified and is registered in the Trazo Carbon Registry. "
            "The carbon offsets represented by this certificate have been retired and cannot be "
            "used for any other purpose."
        )
        
        if self.require_blockchain_verification:
            verification_text += " This certificate has been verified using blockchain technology for enhanced security and immutability."
        else:
            verification_text += " WARNING: This certificate was generated in development mode without blockchain verification."
            
        story.append(Paragraph(verification_text, verification_style))

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