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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings

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
