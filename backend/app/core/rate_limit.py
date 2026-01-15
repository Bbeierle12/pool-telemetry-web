"""Rate limiting configuration using SlowAPI."""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter instance using client IP for rate limiting
limiter = Limiter(key_func=get_remote_address)

# Rate limit constants
RATE_LIMIT_DEFAULT = "100/minute"  # General endpoints
RATE_LIMIT_AUTH = "10/minute"      # Login attempts
RATE_LIMIT_AI = "20/minute"        # AI-powered endpoints (expensive)
RATE_LIMIT_UPLOAD = "5/minute"     # File uploads
RATE_LIMIT_EXPORT = "10/minute"    # Data exports
