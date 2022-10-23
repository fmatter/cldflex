"""Tests for the cldflex.my_module module.
"""
import pandas as pd

from cldflex.flex2csv import convert


def test_convert(flextext, monkeypatch, tmp_path, data):
    convert(flextext, output_dir=tmp_path)

    for filename in [
        "sentences.csv",
        "sentence_slices.csv",
        "wordforms.csv",
        "texts.csv",
    ]:
        df1 = pd.read_csv(tmp_path / filename)
        df2 = pd.read_csv(data / "output" / filename)

        for col in df1.columns:
            if col not in df2.columns:
                df1.drop(columns=[col], inplace=True)

        df1 = df1[sorted(df1.columns)]
        df2 = df2[sorted(df2.columns)]

        pd.testing.assert_frame_equal(df1, df2)


def test_with_lexicon(flextext, monkeypatch, tmp_path, data):
    convert(flextext, lexicon_file=data / "output" / "morphs.csv", output_dir=tmp_path)

    for filename in [
        "sentences.csv",
        "sentence_slices.csv",
        "wordforms.csv",
        "texts.csv",
        "form_slices.csv",
    ]:
        df1 = pd.read_csv(tmp_path / filename)
        df2 = pd.read_csv(data / "output" / filename)

        for col in df1.columns:
            if col not in df2.columns:
                df1.drop(columns=[col], inplace=True)

        df1 = df1[sorted(df1.columns)]
        df2 = df2[sorted(df2.columns)]

        pd.testing.assert_frame_equal(df1, df2)
