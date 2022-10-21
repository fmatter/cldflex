"""Tests for the cldflex.my_module module.
"""
import pandas as pd
from cldflex.lift2csv import convert


def test_lift(data, tmp_path):
    convert(lift_file=data / "ikpeng_lift.lift", output_dir=tmp_path)

    for filename in [
        "morphs.csv",
        # "morphemes.csv",
    ]:
        df1 = pd.read_csv(tmp_path / filename)
        df2 = pd.read_csv(data / "output" / filename)

        for col in df1.columns:
            if col not in df2.columns:
                df1.drop(columns=[col], inplace=True)

        df1 = df1[sorted(df1.columns)]
        df2 = df2[sorted(df2.columns)]

        print(df1)
        print(df2)
        pd.testing.assert_frame_equal(df1, df2)