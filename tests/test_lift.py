"""Tests for the cldflex.my_module module.
"""
import pytest

from cldflex.lift2csv import convert


def test_convert(data, tmp_path):
    convert(lift_file=data/"ikpeng_lift.lift", output_dir=tmp_path)

    with open(tmp_path / "morphs.csv", "r", encoding="utf-8") as f:
        lexicon = f.read()

    with open(data / "output" / "morphs.csv", "r", encoding="utf-8") as f:
        lexicon2 = f.read()
    assert lexicon == lexicon2