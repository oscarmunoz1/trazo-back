"""
MVP-aligned photo evidence service for enhanced self-reported verification.

This service handles secure photo upload, validation, and storage for carbon offset evidence.
Designed for simplicity and security while maintaining transparency for Trazo's QR-based
agricultural carbon tracking mission.
"""

import os
import uuid
import hashlib
import mimetypes
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image, ExifTags
import logging
from datetime import datetime, timezone
import json

logger = logging.getLogger(__name__)


class PhotoEvidenceService:
    """
    Service for handling photo evidence uploads with MVP-aligned security and validation.
    
    Features:
    - Secure file validation and sanitization
    - Image format conversion and compression
    - EXIF data extraction for verification
    - Simple cloud storage integration
    - Evidence integrity checking
    """
    
    # MVP Configuration - Simple but secure
    ALLOWED_MIME_TYPES = [
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/webp'
    ]
    
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max
    MAX_PHOTOS_PER_ENTRY = 5  # Reasonable limit for MVP
    
    # Image processing settings
    MAX_DIMENSION = 2048  # Resize large images to save storage
    JPEG_QUALITY = 85  # Good quality vs file size balance
    
    def __init__(self):
        """Initialize the photo evidence service."""
        self.storage_path = 'carbon_evidence/photos/'
        
    def validate_photo(self, file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Validate uploaded photo for security and format compliance.
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            
        Returns:
            Dict with validation results
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'metadata': {}
        }
        
        try:
            # File size validation
            if len(file_data) > self.MAX_FILE_SIZE:
                result['errors'].append(f'File too large. Maximum size: {self.MAX_FILE_SIZE / (1024*1024):.1f}MB')
                return result
            
            if len(file_data) < 1024:  # Minimum 1KB
                result['errors'].append('File too small. Minimum size: 1KB')
                return result
            
            # File extension validation
            file_ext = os.path.splitext(filename.lower())[1]
            if file_ext not in self.ALLOWED_EXTENSIONS:
                result['errors'].append(f'Invalid file extension. Allowed: {", ".join(self.ALLOWED_EXTENSIONS)}')
                return result
            
            # MIME type validation
            detected_mime = mimetypes.guess_type(filename)[0]
            if detected_mime not in self.ALLOWED_MIME_TYPES:
                result['errors'].append(f'Invalid file type. Allowed: {", ".join(self.ALLOWED_MIME_TYPES)}')
                return result
            
            # Image validation with PIL
            try:
                image = Image.open(ContentFile(file_data))
                image.verify()  # Verify it's a valid image
                
                # Re-open for metadata extraction (verify() closes the image)
                image = Image.open(ContentFile(file_data))
                
                # Extract basic metadata
                result['metadata'] = {
                    'format': image.format,
                    'mode': image.mode,
                    'size': image.size,
                    'filename': filename
                }
                
                # Extract EXIF data for verification (if available)
                exif_data = self._extract_exif_data(image)
                if exif_data:
                    result['metadata']['exif'] = exif_data
                
                # Check minimum dimensions
                width, height = image.size
                if width < 200 or height < 200:
                    result['warnings'].append('Image dimensions are quite small. Consider using higher resolution photos for better evidence.')
                
            except Exception as e:
                result['errors'].append(f'Invalid image file: {str(e)}')
                return result
            
            # File format security check - look for embedded content
            if self._has_suspicious_content(file_data):
                result['errors'].append('File contains suspicious content and cannot be uploaded')
                return result
            
            result['valid'] = True
            logger.info(f"Photo validation passed: {filename} ({len(file_data)} bytes)")
            
        except Exception as e:
            logger.error(f"Photo validation error: {e}")
            result['errors'].append(f'Validation error: {str(e)}')
        
        return result
    
    def process_and_store_photo(self, file_data: bytes, filename: str, 
                               carbon_entry_id: int, user_id: int) -> Dict[str, Any]:
        """
        Process, optimize, and store photo evidence securely.
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            carbon_entry_id: Associated carbon entry ID
            user_id: User uploading the photo
            
        Returns:
            Dict with storage results including URL
        """
        result = {
            'success': False,
            'photo_url': None,
            'photo_id': None,
            'errors': [],
            'metadata': {}
        }
        
        try:
            # First validate the photo
            validation_result = self.validate_photo(file_data, filename)
            if not validation_result['valid']:
                result['errors'] = validation_result['errors']
                return result
            
            # Generate unique filename
            file_ext = os.path.splitext(filename.lower())[1]
            unique_id = str(uuid.uuid4())
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"carbon_{carbon_entry_id}_{timestamp}_{unique_id}{file_ext}"
            
            # Process image for optimization
            processed_data = self._process_image(file_data, file_ext)
            
            # Store file
            file_path = os.path.join(self.storage_path, safe_filename)
            stored_name = default_storage.save(file_path, ContentFile(processed_data))
            
            # Generate public URL
            if hasattr(default_storage, 'url'):
                photo_url = default_storage.url(stored_name)
            else:
                # Fallback for local storage
                photo_url = f"/media/{stored_name}"
            
            # Create metadata record
            metadata = {
                'original_filename': filename,
                'stored_filename': safe_filename,
                'file_size': len(processed_data),
                'upload_timestamp': datetime.now(timezone.utc).isoformat(),
                'carbon_entry_id': carbon_entry_id,
                'uploaded_by': user_id,
                'file_hash': hashlib.sha256(processed_data).hexdigest(),
                'validation_metadata': validation_result['metadata']
            }
            
            result.update({
                'success': True,
                'photo_url': photo_url,
                'photo_id': unique_id,
                'metadata': metadata
            })
            
            logger.info(f"Photo stored successfully: {safe_filename} for carbon entry {carbon_entry_id}")
            
        except Exception as e:
            logger.error(f"Photo storage error: {e}")
            result['errors'].append(f'Storage error: {str(e)}')
        
        return result
    
    def _extract_exif_data(self, image: Image) -> Optional[Dict[str, Any]]:
        """
        Extract useful EXIF data from image for verification purposes.
        
        Args:
            image: PIL Image object
            
        Returns:
            Dict with extracted EXIF data or None
        """
        try:
            exif_dict = image._getexif()
            if not exif_dict:
                return None
            
            # Extract useful metadata for verification
            useful_data = {}
            
            for tag_id, value in exif_dict.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                
                # Extract specific useful tags
                if tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                    useful_data[tag] = str(value)
                elif tag in ['Make', 'Model']:  # Camera info
                    useful_data[tag] = str(value)
                elif tag in ['GPSInfo']:  # Location data (if available)
                    useful_data['has_gps'] = True
                elif tag in ['Software']:  # Editing software detection
                    useful_data[tag] = str(value)
            
            return useful_data if useful_data else None
            
        except Exception as e:
            logger.warning(f"EXIF extraction failed: {e}")
            return None
    
    def _process_image(self, file_data: bytes, file_ext: str) -> bytes:
        """
        Process and optimize image for storage.
        
        Args:
            file_data: Raw image bytes
            file_ext: File extension
            
        Returns:
            Processed image bytes
        """
        try:
            image = Image.open(ContentFile(file_data))
            
            # Convert to RGB if necessary (handles RGBA, P, etc.)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                rgb_image.paste(image, mask=image.split()[-1] if len(image.split()) == 4 else None)
                image = rgb_image
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if too large
            if max(image.size) > self.MAX_DIMENSION:
                image.thumbnail((self.MAX_DIMENSION, self.MAX_DIMENSION), Image.Resampling.LANCZOS)
            
            # Save optimized version
            output = ContentFile(b'')
            
            if file_ext.lower() in ['.jpg', '.jpeg']:
                image.save(output, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
            elif file_ext.lower() == '.png':
                image.save(output, format='PNG', optimize=True)
            elif file_ext.lower() == '.webp':
                image.save(output, format='WEBP', quality=self.JPEG_QUALITY, optimize=True)
            else:
                # Default to JPEG for unknown formats
                image.save(output, format='JPEG', quality=self.JPEG_QUALITY, optimize=True)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            # Return original data if processing fails
            return file_data
    
    def _has_suspicious_content(self, file_data: bytes) -> bool:
        """
        Basic check for suspicious content in uploaded files.
        
        Args:
            file_data: File bytes to check
            
        Returns:
            True if suspicious content detected
        """
        try:
            # Check for executable signatures
            suspicious_signatures = [
                b'\x4D\x5A',  # PE executable
                b'\x7F\x45\x4C\x46',  # ELF executable
                b'\xFE\xED\xFA',  # Mach-O executable
                b'<?php',  # PHP code
                b'<script',  # JavaScript
                b'javascript:',  # JavaScript URL
            ]
            
            # Check first 1KB of file
            check_data = file_data[:1024].lower()
            
            for sig in suspicious_signatures:
                if sig.lower() in check_data:
                    logger.warning("Suspicious content detected in uploaded file")
                    return True
            
            return False
            
        except Exception:
            # If we can't check, be safe and reject
            return True
    
    def delete_photo(self, photo_url: str) -> bool:
        """
        Delete photo from storage.
        
        Args:
            photo_url: URL or path of photo to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            # Extract filename from URL
            if photo_url.startswith('/media/'):
                file_path = photo_url[7:]  # Remove '/media/' prefix
            elif photo_url.startswith('http'):
                file_path = photo_url.split('/')[-1]
            else:
                file_path = photo_url
            
            if default_storage.exists(file_path):
                default_storage.delete(file_path)
                logger.info(f"Photo deleted: {file_path}")
                return True
            else:
                logger.warning(f"Photo not found for deletion: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Photo deletion error: {e}")
            return False
    
    def verify_photo_integrity(self, photo_url: str, expected_hash: str) -> bool:
        """
        Verify photo hasn't been tampered with.
        
        Args:
            photo_url: Photo URL
            expected_hash: Expected SHA256 hash
            
        Returns:
            True if integrity check passes
        """
        try:
            # Extract file path from URL
            if photo_url.startswith('/media/'):
                file_path = photo_url[7:]
            else:
                file_path = photo_url.split('/')[-1]
            
            if not default_storage.exists(file_path):
                return False
            
            # Read file and compute hash
            with default_storage.open(file_path, 'rb') as f:
                file_data = f.read()
                actual_hash = hashlib.sha256(file_data).hexdigest()
            
            return actual_hash == expected_hash
            
        except Exception as e:
            logger.error(f"Photo integrity check error: {e}")
            return False


# Singleton instance for easy importing
photo_evidence_service = PhotoEvidenceService()