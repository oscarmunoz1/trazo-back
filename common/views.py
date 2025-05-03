from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
from redis import Redis
from redis.exceptions import RedisError
import logging
import datetime
import boto3
import uuid
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Create your views here.

def health_check(request):
    # Check database connection
    db_healthy = True
    try:
        connections['default'].cursor()
    except OperationalError as e:
        db_healthy = False
        logger.error("Database connection failed: " + str(e))

    status = 200 if (db_healthy) else 503
    
    response = {
        "status": "healthy" if status == 200 else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    return JsonResponse(response, status=status)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_upload_urls(request):
    """
    Generate pre-signed URLs for direct S3 uploads.
    
    Expected request format:
    {
        "files": [
            {"name": "image1.jpg", "type": "image/jpeg", "size": 12345},
            {"name": "image2.png", "type": "image/png", "size": 67890}
        ],
        "entity_type": "establishment", // or "user", "company", "parcel", etc.
        "entity_id": "123" // optional, for updates to existing entities
    }
    """
    files_info = request.data.get('files', [])
    entity_type = request.data.get('entity_type', 'misc')
    entity_id = request.data.get('entity_id', '')
    
    # Check if AWS settings are configured
    if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_STORAGE_BUCKET_NAME]):
        return Response(
            {"error": "S3 storage is not properly configured"}, 
            status=500
        )
    
    try:
        s3_client = boto3.client(
            's3',
            region_name=settings.AWS_S3_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        urls_and_keys = []
        for file_info in files_info:
            file_name = file_info.get('name')
            file_type = file_info.get('type')
            
            # Create a unique key for the file based on entity type
            folder = f"{entity_type}s"
            if entity_id:
                key = f"{folder}/{entity_id}/{uuid.uuid4()}-{file_name}"
            else:
                # For new entities, use user ID or timestamp
                key = f"{folder}/new-{request.user.id}-{uuid.uuid4()}-{file_name}"
            
            # Generate a pre-signed URL for this specific file
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': key,
                    'ContentType': file_type
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            
            urls_and_keys.append({
                'uploadUrl': presigned_url,
                's3Key': key,
                'publicUrl': f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
            })
        
        return Response(urls_and_keys)
    
    except Exception as e:
        logger.error(f"Error generating pre-signed URLs: {str(e)}")
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_presigned_url(request):
    """Generate a pre-signed URL for client-side S3 upload"""
    filename = request.data.get('filename')
    file_type = request.data.get('fileType')
    folder = request.data.get('folder', 'uploads')
    
    if not filename or not file_type:
        return Response({'error': 'Filename and fileType are required'}, status=400)
    
    # Generate a unique key for the file
    unique_filename = f"{uuid.uuid4()}-{filename}"
    key = f"media/{folder}/{unique_filename}"
    
    # Only generate S3 URLs in production environment
    if settings.DEFAULT_FILE_STORAGE == 'storages.backends.s3boto3.S3Boto3Storage':
        try:
            # Generate the presigned URL
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': key,
                    'ContentType': file_type,
                    'ACL': 'public-read'
                },
                ExpiresIn=3600  # URL expires after 1 hour
            )
            
            file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"
            
            return Response({
                'presigned_url': presigned_url,
                's3_key': key,
                'file_url': file_url
            })
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    else:
        # In development, return a placeholder since we'll handle uploads via standard form
        return Response({
            'development': True,
            'message': 'Running in development mode - use form upload instead'
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def local_file_upload(request):
    """Handle file uploads in development environment"""
    # Log request details for debugging
    logger.debug(f"Request method: {request.method}")
    logger.debug(f"Content type: {request.content_type}")
    logger.debug(f"Request FILES: {request.FILES}")
    logger.debug(f"Request headers: {request.headers}")
    
    # If Content-Type is application/json but we have FILES, Django's parser has already handled it
    if request.content_type and 'application/json' in request.content_type and request.FILES:
        logger.info("Request has application/json Content-Type but contains files. Proceeding anyway.")
    
    try:
        # Check if we have files in the request
        if not request.FILES:
            logger.error("No files found in request.FILES")
            # Try to get raw request body if available
            try:
                if hasattr(request, '_body'):
                    logger.error(f"Raw request body: {request._body[:100]}...")
            except Exception as e:
                logger.error(f"Could not access raw body: {str(e)}")
                
            return Response({'error': 'No files were submitted'}, status=400)
        
        # Get the file from the request
        upload_file = request.FILES.get('file')
        if not upload_file:
            logger.error(f"No file field found. Available fields: {list(request.FILES.keys())}")
            return Response({
                'error': 'No file found with key "file"',
                'available_keys': list(request.FILES.keys())
            }, status=400)
        
        logger.info(f"Processing file upload: {upload_file.name}, size: {upload_file.size}, type: {upload_file.content_type}")
        
        # Create unique filename to prevent overwrites
        filename = f"{uuid.uuid4()}-{upload_file.name}"
        
        # Save the file
        save_path = f'uploads/{filename}'
        path = default_storage.save(save_path, ContentFile(upload_file.read()))
        
        # Get the full URL
        file_url = request.build_absolute_uri(settings.MEDIA_URL + path)
        logger.info(f"File saved to {path}, URL: {file_url}")
        
        # Return success response
        return Response({
            'file_url': file_url,
            'path': path,
            'success': True
        })
        
    except Exception as e:
        logger.exception(f"Error uploading file: {str(e)}")
        
        # Check if this is a UTF-8 decode error, which is common with binary file uploads
        if "utf-8" in str(e).lower() and "decode" in str(e).lower():
            logger.error("This appears to be a binary data handling error. Make sure the request is properly formed as multipart/form-data.")
            
        return Response({
            'error': f'File upload failed: {str(e)}',
            'detail': 'This may be a Content-Type mismatch. Ensure your request is using multipart/form-data.'
        }, status=500)
