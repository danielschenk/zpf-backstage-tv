from urllib.parse import urlparse


def is_safe_url(target):
    """Tests if target is safe to redirect to"""
    parsed = urlparse(target)
    # Only allow relative URLs
    return not parsed.scheme and not parsed.netloc
