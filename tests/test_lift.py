"""Tests for the cldflex.my_module module.
"""
import pytest

from cldflex.lift2csv import convert


def test_convert():
    with pytest.raises(FileNotFoundError):
        convert("nothing")
