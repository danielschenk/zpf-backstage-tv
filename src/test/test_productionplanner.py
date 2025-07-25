import pytest
from ..productionplanner import remove_friends_night_tag


@pytest.mark.parametrize(
    "input, output",
    [
        ("Act @ Vrienden", "Act"),
        ("Act [VRIENDEN]", "Act"),
        ("Act [VRIENDENAVOND]", "Act"),
        ("Act [VRIENDEN AVOND]", "Act"),
        ("Act@vrienden", "Act"),
        ("Act (vrienden en vriendinnen)", "Act (vrienden en vriendinnen)"),
    ],
)
def test_remove_friends_night_tag(input, output):
    assert remove_friends_night_tag(input) == output
