from click.testing import CliRunner
from cldflex.cli import flex2csv, lift2csv
from pycldf import Dataset
from pathlib import Path
import shutil


def test_sentences(data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        flex2csv,
        [str((data / "ikpeng.flextext").resolve()), f"--output", tmp_path, "--cldf"],
    )
    assert result.exit_code == 0
    md_path = Path(tmp_path / "cldf/metadata.json")
    assert md_path.is_file()
    ds = Dataset.from_metadata(md_path)
    assert ds.validate()
    assert Path(tmp_path / "wordforms.csv").is_file()
    assert Path(tmp_path / "sentences.csv").is_file()


def test_sentences_with_lexicon(data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shutil.copy(data / "ikpeng.flextext", tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        flex2csv,
        [
            str((tmp_path / "ikpeng.flextext").resolve()),
            "--lexicon",
            str((data / "output/morphs.csv")),
            f"--output",
            tmp_path,
            "--cldf",
            "--conf",
            str((data / "config1.yaml")),
        ],
    )
    assert result.exit_code == 0
    md_path = Path(tmp_path / "cldf/metadata.json")
    assert md_path.is_file()
    ds = Dataset.from_metadata(md_path)
    assert ds.validate()


def test_lift(data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        lift2csv,
        [
            str((data / "ikpeng_lift.lift").resolve()),
            f"--output",
            tmp_path,
            "--cldf",
            "--conf",
            str((data / "config1.yaml")),
        ],
    )
    assert result.exit_code == 0
    assert Path(tmp_path / "senses.csv").is_file()
    assert Path(tmp_path / "morphs.csv").is_file()
    assert Path(tmp_path / "morphemes.csv").is_file()
    md_path = Path(tmp_path / "cldf/metadata.json")
    assert md_path.is_file()
    ds = Dataset.from_metadata(md_path)
    assert ds.validate()
