import pytest
from ..util import is_safe_url


@pytest.mark.parametrize(
    "url, is_safe",
    [
        ("/foo", True),
        ("/foo/bar", True),
        ("foo.com", True),
        ("foo", True),
        ("//foo", False),
        ("http://foo", False),
        ("http://foo.com", False),
    ],
)
def test_is_safe_url(url, is_safe):
    assert is_safe_url(url) == is_safe
