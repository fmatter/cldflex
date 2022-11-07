from click.testing import CliRunner
from cldflex.cli import flex2csv, lift2csv
from pycldf import Dataset
from pathlib import Path
import shutil
import pandas as pd


def check_filelist(path, checklist):
    file_list = [x.name for x in Path(path).iterdir()]
    for d in ["requirements.txt", "metadata.json", ".gitattributes", "README.md"]:
        if d in file_list:
            file_list.remove(d)
    print(sorted(checklist))
    print(sorted(file_list))
    assert sorted(checklist) == sorted(file_list)


def check_cldf(path):
    md_path = Path(path / "cldf/metadata.json")
    assert md_path.is_file()
    ds = Dataset.from_metadata(md_path)
    assert ds.validate()
    return ds


def run_flextext(path, monkeypatch, data, config=None, lexicon=True, cldf=True):
    monkeypatch.chdir(path)
    runner = CliRunner()
    commands = [str((data / "ikpeng.flextext").resolve()), f"--output", path]
    if lexicon:
        commands.extend(["--lexicon", str((data / "output/morphs.csv"))])
    if cldf:
        commands.extend(["--cldf"])
    if config:
        commands.extend(["--conf", str((data / f"{config}.yaml"))])
    return runner.invoke(flex2csv, commands)


def test_sentences1(data, tmp_path, monkeypatch):
    run_flextext(tmp_path, monkeypatch, data, lexicon=False)
    check_cldf(tmp_path)
    check_filelist(
        tmp_path,
        ["wordforms.csv", "sentences.csv", "sentence_slices.csv", "texts.csv", "cldf"],
    )
    check_filelist(
        tmp_path / "cldf",
        ["languages.csv", "examples.csv", "forms.csv", "parameters.csv", "ExampleSlices", "TextTable"],
    )


def test_sentences_with_lexicon_both_slices(data, tmp_path, monkeypatch):
    result = run_flextext(tmp_path, monkeypatch, data, "config1")
    assert result.exit_code == 0
    check_cldf(tmp_path)
    check_filelist(
        tmp_path,
        [
            "wordforms.csv",
            "sentences.csv",
            "sentence_slices.csv",
            "texts.csv",
            "cldf",
            "form_slices.csv",
        ],
    )
    check_filelist(
        tmp_path / "cldf",
        [
            "MorphsetTable",
            "FormSlices",
            "examples.csv",
            "MorphTable",
            "forms.csv",
            "parameters.csv",
            "ExampleSlices",
            "languages.csv",
            "TextTable",
        ],
    )


def test_sentences_with_lexicon_no_example_slices(data, tmp_path, monkeypatch):
    result = run_flextext(tmp_path, monkeypatch, data, "config2")
    assert result.exit_code == 0
    check_cldf(tmp_path)
    check_filelist(
        tmp_path / "cldf",
        [
            "MorphsetTable",
            "examples.csv",
            "FormSlices",
            "languages.csv",
            "MorphTable",
            "forms.csv",
            "TextTable",
            "parameters.csv",
        ],
    )


def test_sentences_with_lexicon_no_form_slices(data, tmp_path, monkeypatch):
    result = run_flextext(tmp_path, monkeypatch, data, "config3")
    assert result.exit_code == 0
    check_cldf(tmp_path)
    check_filelist(
        tmp_path / "cldf",
        [
            "MorphsetTable",
            "examples.csv",
            "ExampleSlices",
            "MorphTable",
            "languages.csv",
            "forms.csv",
            "TextTable",
            "parameters.csv",
        ],
    )


def test_sentences_with_lexicon_no_slices(data, tmp_path, monkeypatch):
    result = run_flextext(tmp_path, monkeypatch, data, "config4")
    assert result.exit_code == 0
    check_cldf(tmp_path)
    check_filelist(
        tmp_path / "cldf",
        [
            "languages.csv",
            "MorphsetTable",
            "examples.csv",
            "MorphTable",
            "forms.csv",
            "TextTable",
            "parameters.csv",
        ],
    )


def test_lift(data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        lift2csv,
        [str((data / "ikpeng_lift.lift").resolve()), f"--output", tmp_path, "--cldf"],
    )
    assert result.exit_code == 0
    assert Path(tmp_path / "senses.csv").is_file()
    assert Path(tmp_path / "morphs.csv").is_file()
    assert Path(tmp_path / "morphemes.csv").is_file()
    md_path = Path(tmp_path / "cldf/metadata.json")
    assert md_path.is_file()
    ds = Dataset.from_metadata(md_path)
    assert ds.validate()
