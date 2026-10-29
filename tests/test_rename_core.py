"""Tests for the Qt-independent planning and transaction core."""

import os
from pathlib import Path

import pytest

import rename_utility as ru


def touch(folder: Path, *names: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(name.encode())


def listing(folder: Path) -> list:
    return sorted(os.listdir(folder), key=ru.natural_key)


# --- parsing and naming ----------------------------------------------------

def test_natural_sort_orders_numbers_numerically():
    names = ["f10.hex", "f2.hex", "F1.hex"]
    assert sorted(names, key=ru.natural_key) == ["F1.hex", "f2.hex", "f10.hex"]


@pytest.mark.parametrize("folder, prefix", [
    ("MFLB1S2", "HID01SID02_"),
    ("CMFLB12S3", "HID12SID03_"),
    ("egpb2s1", "HID02SID01_"),
])
def test_auto_prefix_from_folder_name(folder, prefix):
    assert ru.auto_prefix_from_folder_name(folder) == prefix


@pytest.mark.parametrize("folder", ["INLB", "MFLB1", "CMFLB1S2_old", "XMFLB1S2"])
def test_auto_prefix_rejects_other_folders(folder):
    with pytest.raises(ValueError):
        ru.auto_prefix_from_folder_name(folder)


# --- automatic mode --------------------------------------------------------

def test_auto_plans_number_each_folder_from_zero(tmp_path):
    touch(tmp_path / "CMFLB4S2", "HID255SID255_0000.hex", "HID255SID255_0001.hex")
    touch(tmp_path / "EGPB2S1", "x.hex")
    touch(tmp_path / "INLB", "y.hex")
    (tmp_path / "MFLB1S1").mkdir()
    touch(tmp_path, "INLB0000.hex")

    batch = ru.build_auto_rename_plans(str(tmp_path))

    assert [p.display_name for p in batch.plans] == ["CMFLB4S2", "EGPB2S1"]
    assert batch.plans[0].mapping == (
        ("HID255SID255_0000.hex", "HID04SID02_0000.hex"),
        ("HID255SID255_0001.hex", "HID04SID02_0001.hex"),
    )
    assert batch.plans[1].mapping == (("x.hex", "HID02SID01_0000.hex"),)
    assert any("INLB" in w for w in batch.warnings)
    assert any("MFLB1S1" in w for w in batch.warnings)


def test_auto_plans_without_eligible_folders(tmp_path):
    touch(tmp_path / "INLB", "y.hex")
    with pytest.raises(ValueError, match="No eligible"):
        ru.build_auto_rename_plans(str(tmp_path))


# --- preview snapshot ------------------------------------------------------

def test_preview_goes_stale_when_files_change(tmp_path):
    touch(tmp_path / "MFLB1S1", "a.hex")
    snap = ru.create_preview_snapshot(str(tmp_path))
    assert ru.preview_is_current(snap, str(tmp_path))
    touch(tmp_path / "MFLB1S1", "b.hex")
    assert not ru.preview_is_current(snap, str(tmp_path))


def test_preview_goes_stale_when_folder_is_renamed(tmp_path):
    touch(tmp_path / "MFLB1S1", "a.hex")
    snap = ru.create_preview_snapshot(str(tmp_path))
    (tmp_path / "MFLB1S1").rename(tmp_path / "MFLB1S2")
    assert not ru.preview_is_current(snap, str(tmp_path))


def test_auto_plans_reject_existing_target(tmp_path):
    # A non-source entry (here a folder) already holds a target name.
    touch(tmp_path / "MFLB1S1", "a.hex", "b.hex")
    (tmp_path / "MFLB1S1" / "HID01SID01_0001.hex").mkdir()
    with pytest.raises(ValueError, match="HID01SID01_0001.hex"):
        ru.build_auto_rename_plans(str(tmp_path))


# --- transaction -----------------------------------------------------------

def test_atomic_rename_handles_targets_that_are_other_sources(tmp_path):
    # Shifting a sequence down by one: each target is another file's source.
    folder = tmp_path / "MFLB1S1"
    touch(folder, "HID01SID01_0001.hex", "HID01SID01_0002.hex", "HID01SID01_0003.hex")
    batch = ru.build_auto_rename_plans(str(tmp_path))
    assert ru.atomic_batch_rename(batch.plans) == (3, 0)
    assert listing(folder) == [
        "HID01SID01_0000.hex", "HID01SID01_0001.hex", "HID01SID01_0002.hex"]
    assert (folder / "HID01SID01_0002.hex").read_bytes() == b"HID01SID01_0003.hex"


def test_atomic_rename_skips_already_correct_names(tmp_path):
    folder = tmp_path / "EGPB2S1"
    touch(folder, "HID02SID01_0000.hex", "z.hex")
    batch = ru.build_auto_rename_plans(str(tmp_path))
    assert ru.atomic_batch_rename(batch.plans) == (1, 1)
    assert listing(folder) == ["HID02SID01_0000.hex", "HID02SID01_0001.hex"]


def test_atomic_rename_rolls_back_on_failure(tmp_path):
    touch(tmp_path / "MFLB1S1", "a.hex", "b.hex")
    touch(tmp_path / "MFLB1S2", "c.hex")
    batch = ru.build_auto_rename_plans(str(tmp_path))
    before = {p: listing(tmp_path / p) for p in ("MFLB1S1", "MFLB1S2")}

    def explode(step, total):
        if step == total - 1:
            raise RuntimeError("Cancelled")

    with pytest.raises(RuntimeError, match="rolled back"):
        ru.atomic_batch_rename(batch.plans, explode)
    assert {p: listing(tmp_path / p) for p in before} == before
