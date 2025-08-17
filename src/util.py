from urllib.parse import urlparse


def is_safe_url(target):
    """Tests if target is safe to redirect to"""
    # Replace backslashes, which browsers treat as slashes
    target = target.replace("\\", "/")
    parsed = urlparse(target)
    # Only allow relative URLs
    return not parsed.scheme and not parsed.netloc
