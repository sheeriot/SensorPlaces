import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_execution_time(func):
    """
    A decorator that logs the execution time of a function.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        
        view_name = func.__name__
        
        # Check if the first argument is a request object to get more context
        request = None
        if args:
            from django.http import HttpRequest
            if isinstance(args[0], HttpRequest):
                request = args[0]
        
        if request:
            logger.info(
                f"Execution time for '{view_name}' ({request.method} {request.path}): {duration:.4f} seconds"
            )
        else:
            logger.info(
                f"Execution time for '{view_name}': {duration:.4f} seconds"
            )
            
        return result
    return wrapper
