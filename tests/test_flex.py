"""Tests for the cldflex.my_module module.
"""
import pytest

from cldflex.flex2csv import convert


def test_convert(flextext, monkeypatch, tmp_path, data):
    convert(flextext, output_dir=tmp_path)

    with open(tmp_path / "sentences.csv", "r", encoding="utf-8") as f:
        sentences = f.read()

    with open(data / "output" / "sentences.csv", "r", encoding="utf-8") as f:
        sentences2 = f.read()
    assert sentences == sentences2