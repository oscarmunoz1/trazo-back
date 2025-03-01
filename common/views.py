from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
from redis import Redis
from redis.exceptions import RedisError
import logging
import datetime

logger = logging.getLogger(__name__)

# Create your views here.

def health_check(request):
    # Check database connection
    db_healthy = True
    try:
        connections['default'].cursor()
    except OperationalError:
        db_healthy = False
        logger.error("Database connection failed: " + str(e))



    status = 200 if (db_healthy) else 503
    
    response = {
        "status": "healthy" if status == 200 else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    return JsonResponse(response, status=status)
