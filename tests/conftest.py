import pytest
from pathlib import Path

@pytest.fixture(scope="module")
def data():
    return Path(__file__).parent / "data"

@pytest.fixture
def flextext(data):
    return data / "ikpeng.flextext"