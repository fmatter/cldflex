"""Tests for the cldflex.my_module module.
"""
import pytest
import pandas as pd

from cldflex.flex2csv import convert


def test_convert(flextext, monkeypatch, tmp_path, data):
    convert(flextext, output_dir=tmp_path)

    for filename in [
        "sentences.csv",
        # "sentence_slices.csv",
        # "wordforms.csv",
        # "texts.csv",
    ]:
        df1 = pd.read_csv(tmp_path / filename)
        df2 = pd.read_csv(data / "output" / filename)
        pd.testing.assert_frame_equal(df1, df2)


def test_with_lexicon(flextext, monkeypatch, tmp_path, data):
    convert(flextext, lexicon_file=data / "output" / "morphs.csv", output_dir=tmp_path)

    with open(tmp_path / "form_slices.csv", "r", encoding="utf-8") as f:
        sl1 = f.read()

    with open(data / "output" / "form_slices.csv", "r", encoding="utf-8") as f:
        sl2 = f.read()
    assert sl1 == sl2
