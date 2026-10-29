"""Standalone, transactional HEX file rename utility.

Requires ``qtpy`` and a supported Qt binding (for example PySide6 or PyQt5).
The core planning and transaction functions are deliberately independent of Qt.
"""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
import re
import sys
import uuid
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from qtpy import QtCore, QtGui, QtWidgets


FIRST_NAME_RE = re.compile(r"^(?P<prefix>.*?)(?P<num>\d+)$")
AUTO_RENAME_FOLDER_RE = re.compile(
    r"^(?:(?:C)?MFLB|EGPB)(?P<hid>\d+)S(?P<sid>\d+)$", re.IGNORECASE
)


def natural_key(value: str) -> List[object]:
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", value)]


@dataclass(frozen=True)
class RenameFolderPlan:
    dir_path: str
    display_name: str
    mapping: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class RenameBatchPlan:
    plans: Tuple[RenameFolderPlan, ...]
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class PreviewSnapshot:
    """Everything whose change makes a displayed preview unsafe to apply."""

    root_path: str
    automatic: bool
    target_input: str
    plans: Tuple[RenameFolderPlan, ...]
    warnings: Tuple[str, ...]
    file_signatures: Tuple[Tuple[str, str, int, int], ...]


def parse_first_name(user_input: str) -> Tuple[str, int, int]:
    text = user_input.strip()
    base = text[:-4] if text.lower().endswith(".hex") else text
    match = FIRST_NAME_RE.fullmatch(base)
    if not match:
        raise ValueError("First name must end with digits, e.g. HID04SID02_0000")
    digits = match.group("num")
    return match.group("prefix"), int(digits), len(digits)


def collect_hex_files_non_recursive(dir_path: str) -> List[str]:
    with os.scandir(dir_path) as entries:
        files = [entry.name for entry in entries
                 if entry.is_file() and entry.name.lower().endswith(".hex")]
    return sorted(files, key=natural_key)


def build_mapping(files: Sequence[str], prefix: str, start: int,
                  pad: int) -> List[Tuple[str, str]]:
    return [(old, f"{prefix}{start + index:0{pad}d}{Path(old).suffix}")
            for index, old in enumerate(files)]


def build_auto_mapping(files: Sequence[str], prefix: str) -> List[Tuple[str, str]]:
    return [(old, f"{prefix}{index:04d}.hex")
            for index, old in enumerate(files)]


def auto_prefix_from_folder_name(folder_name: str) -> str:
    match = AUTO_RENAME_FOLDER_RE.fullmatch(folder_name)
    if not match:
        raise ValueError(
            f"Invalid subfolder name '{folder_name}'. Expected MFLB<number>S<number> "
            "CMFLB<number>S<number>, or EGPB<number>S<number>."
        )
    return f"HID{int(match.group('hid')):02d}SID{int(match.group('sid')):02d}_"


def validate_mapping(dir_path: str,
                     mapping: Sequence[Tuple[str, str]]) -> None:
    target_keys = [target.casefold() for _old, target in mapping]
    if len(target_keys) != len(set(target_keys)):
        raise ValueError("Generated new names contain duplicates. Adjust your input.")

    existing = {name.casefold(): name for name in os.listdir(dir_path)}
    old_keys = {old.casefold() for old, _new in mapping}
    missing = [old for old, _new in mapping if old.casefold() not in existing]
    if missing:
        raise FileNotFoundError("Source files no longer exist:\n  - " +
                                "\n  - ".join(missing))
    clashes = sorted(
        {existing[new.casefold()] for old, new in mapping
         if new.casefold() in existing and new.casefold() not in old_keys},
        key=natural_key,
    )
    if clashes:
        raise FileExistsError("Target names already exist:\n  - " +
                              "\n  - ".join(clashes))


def build_manual_plan(folder: str, first_name: str) -> RenameBatchPlan:
    files = collect_hex_files_non_recursive(folder)
    if not files:
        raise ValueError("No .hex files found in the selected folder.")
    prefix, start, pad = parse_first_name(first_name)
    mapping = tuple(build_mapping(files, prefix, start, pad))
    validate_mapping(folder, mapping)
    return RenameBatchPlan(
        (RenameFolderPlan(os.path.abspath(folder), Path(folder).name, mapping),), ()
    )


def build_auto_rename_plans(root_path: str) -> RenameBatchPlan:
    with os.scandir(root_path) as entries:
        folders = sorted((entry for entry in entries if entry.is_dir()),
                         key=lambda entry: natural_key(entry.name))
    if not folders:
        raise ValueError("The selected root folder contains no immediate subfolders.")

    plans: List[RenameFolderPlan] = []
    warnings: List[str] = []
    for folder in folders:
        try:
            prefix = auto_prefix_from_folder_name(folder.name)
        except ValueError as exc:
            warnings.append(f"Skipped unrelated subfolder: {exc}")
            continue
        files = collect_hex_files_non_recursive(folder.path)
        if not files:
            warnings.append(f"Skipped empty subfolder '{folder.name}': no .hex files.")
            continue
        mapping = tuple(build_auto_mapping(files, prefix))
        try:
            validate_mapping(folder.path, mapping)
        except Exception as exc:
            raise ValueError(f"Subfolder '{folder.name}': {exc}") from exc
        plans.append(RenameFolderPlan(os.path.abspath(folder.path), folder.name, mapping))

    if not plans:
        detail = "\n  - ".join(warnings)
        raise ValueError(
            "No eligible .hex files were found in valid immediate "
            "MFLB/CMFLB/EGPB subfolders."
            + (f"\n  - {detail}" if detail else "")
        )
    return RenameBatchPlan(tuple(plans), tuple(warnings))


def _signatures(plans: Sequence[RenameFolderPlan]) -> Tuple[Tuple[str, str, int, int], ...]:
    result = []
    for plan in plans:
        for old, _new in plan.mapping:
            stat = os.stat(os.path.join(plan.dir_path, old))
            result.append((plan.dir_path, old, stat.st_size, stat.st_mtime_ns))
    return tuple(result)


def create_preview_snapshot(root_path: str, automatic: bool,
                            target_input: str = "") -> PreviewSnapshot:
    root = os.path.abspath(root_path)
    batch = (build_auto_rename_plans(root) if automatic
             else build_manual_plan(root, target_input))
    return PreviewSnapshot(root, automatic, target_input.strip(), batch.plans,
                           batch.warnings, _signatures(batch.plans))


def preview_is_current(snapshot: PreviewSnapshot, root_path: str,
                       automatic: bool, target_input: str = "") -> bool:
    try:
        current = create_preview_snapshot(root_path, automatic, target_input)
    except (OSError, ValueError):
        return False
    return current == snapshot


def atomic_batch_rename(
    plans: Sequence[RenameFolderPlan],
    progress_cb: Optional[Callable[[int, int], None]] = None,
    rollback_progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[int, int]:
    """Apply all plans as one two-stage transaction, or restore every source."""
    token = uuid.uuid4().hex[:8]
    operations: List[Tuple[str, str, str, str]] = []
    skipped = 0
    for plan in plans:
        for old, new in plan.mapping:
            if old == new:
                skipped += 1
                continue
            temp = f".__renametmp_{token}_{len(operations):06d}.tmp"
            while os.path.exists(os.path.join(plan.dir_path, temp)):
                temp = f".__renametmp_{token}_{len(operations):06d}_{uuid.uuid4().hex}.tmp"
            operations.append((plan.dir_path, old, temp, new))

    total = len(operations) * 2
    staged: List[Tuple[str, str, str, str]] = []
    finalized: List[Tuple[str, str, str, str]] = []
    try:
        for operation in operations:
            folder, old, temp, _new = operation
            os.replace(os.path.join(folder, old), os.path.join(folder, temp))
            staged.append(operation)
            if progress_cb:
                progress_cb(len(staged), total)
        for operation in operations:
            folder, _old, temp, new = operation
            os.replace(os.path.join(folder, temp), os.path.join(folder, new))
            finalized.append(operation)
            if progress_cb:
                progress_cb(len(operations) + len(finalized), total)
    except Exception as original:
        rollback_errors = []
        # Move completed final names back to their temporary slots first.
        for folder, _old, temp, new in reversed(finalized):
            try:
                os.replace(os.path.join(folder, new), os.path.join(folder, temp))
            except Exception as exc:
                rollback_errors.append(f"{new} -> {temp}: {exc}")
        for index, (folder, old, temp, _new) in enumerate(reversed(staged), 1):
            try:
                os.replace(os.path.join(folder, temp), os.path.join(folder, old))
            except Exception as exc:
                rollback_errors.append(f"{temp} -> {old}: {exc}")
            if rollback_progress_cb:
                rollback_progress_cb(index, len(staged))
        message = str(original)
        if rollback_errors:
            message += "\nRollback incomplete. Manual recovery is required:\n  - " + \
                       "\n  - ".join(rollback_errors)
        elif message == "Cancelled":
            message = "Cancelled; all completed changes were rolled back."
        else:
            message += "\nAll completed changes were rolled back."
        raise RuntimeError(message) from original
    return len(operations), skipped


class RenameWorker(QtCore.QThread):
    progress = QtCore.Signal(int, int)
    completed = QtCore.Signal(int, int, int)
    failed = QtCore.Signal(str)

    def __init__(self, plans: Sequence[RenameFolderPlan], parent=None) -> None:
        super().__init__(parent)
        self.plans = tuple(plans)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            total_files = sum(len(plan.mapping) for plan in self.plans)

            def report(step: int, total: int) -> None:
                if self._cancel_requested:
                    raise RuntimeError("Cancelled")
                self.progress.emit(step, total)

            def report_rollback(step: int, total: int) -> None:
                self.progress.emit(step, total)

            renamed, skipped = atomic_batch_rename(
                self.plans, report, report_rollback
            )
            self.completed.emit(renamed, skipped, total_files)
        except Exception as exc:
            self.failed.emit(str(exc))


class LogEmitter(QtCore.QObject):
    message = QtCore.Signal(int, str)


class QtLogHandler(logging.Handler):
    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        self.emitter.message.emit(record.levelno, self.format(record))


class FileRenameWidget(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.snapshot: Optional[PreviewSnapshot] = None
        self.worker: Optional[RenameWorker] = None
        self.log_emitter = LogEmitter()
        self.logger = logging.getLogger(f"rename_utility.{id(self)}")
        self.logger.setLevel(logging.INFO)
        handler = QtLogHandler(self.log_emitter)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
        self.logger.addHandler(handler)
        self.log_emitter.message.connect(self._append_log)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)
        controls = QtWidgets.QGroupBox("HEX sequence rename")
        grid = QtWidgets.QGridLayout(controls)
        self.folder_edit = QtWidgets.QLineEdit()
        self.folder_edit.setPlaceholderText("Select a folder")
        self.browse_btn = QtWidgets.QPushButton("Select Folder…")
        self.open_btn = QtWidgets.QPushButton("Open Folder")
        self.open_btn.setEnabled(False)
        self.first_edit = QtWidgets.QLineEdit()
        self.first_edit.setPlaceholderText("First target, e.g. HID04SID02_0000.hex")
        self.auto_check = QtWidgets.QCheckBox(
            "Automatic mode: immediate MFLB/CMFLB/EGPB subfolders")
        self.preview_btn = QtWidgets.QPushButton("Generate Preview")
        self.rename_btn = QtWidgets.QPushButton("Proceed & Rename")
        self.rename_btn.setObjectName("primary")
        self.rename_btn.setEnabled(False)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setFormat("0% (0/0 steps)")
        grid.addWidget(QtWidgets.QLabel("Folder:"), 0, 0)
        grid.addWidget(self.folder_edit, 0, 1)
        grid.addWidget(self.browse_btn, 0, 2)
        grid.addWidget(self.open_btn, 0, 3)
        grid.addWidget(QtWidgets.QLabel("First target:"), 1, 0)
        grid.addWidget(self.first_edit, 1, 1, 1, 3)
        grid.addWidget(self.auto_check, 2, 1, 1, 3)
        buttons = QtWidgets.QHBoxLayout()
        for button in (self.preview_btn, self.rename_btn, self.cancel_btn):
            buttons.addWidget(button)
        buttons.addStretch()
        grid.addLayout(buttons, 3, 1, 1, 3)
        grid.addWidget(self.progress, 4, 0, 1, 4)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Old name", "New name"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        self.log_view.setFont(QtGui.QFont("Consolas", 9))
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.log_view)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(controls)
        outer.addWidget(splitter, 1)

        self.browse_btn.clicked.connect(self._browse)
        self.open_btn.clicked.connect(self._open_folder)
        self.preview_btn.clicked.connect(self._preview)
        self.rename_btn.clicked.connect(self._rename)
        self.cancel_btn.clicked.connect(self._cancel)
        self.auto_check.toggled.connect(self._mode_changed)
        self.folder_edit.textChanged.connect(self._invalidate)
        self.first_edit.textChanged.connect(self._invalidate)

    def _append_log(self, _level: int, message: str) -> None:
        self.log_view.appendPlainText(message)

    def _invalidate(self, *_args) -> None:
        self.snapshot = None
        self.rename_btn.setEnabled(False)

    def _mode_changed(self, enabled: bool) -> None:
        self.first_edit.setEnabled(not enabled)
        self._invalidate()

    def _browse(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select rename folder")
        if folder:
            self.folder_edit.setText(folder)
            self.open_btn.setEnabled(True)

    def _open_folder(self) -> None:
        folder = self.folder_edit.text().strip()
        if os.path.isdir(folder):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def _preview(self) -> None:
        folder = self.folder_edit.text().strip()
        if not os.path.isdir(folder):
            QtWidgets.QMessageBox.warning(self, "Invalid folder", "Select a valid folder first.")
            return
        try:
            snapshot = create_preview_snapshot(
                folder, self.auto_check.isChecked(), self.first_edit.text())
        except Exception as exc:
            self.logger.error("Preview failed: %s", exc)
            QtWidgets.QMessageBox.critical(self, "Validation error", str(exc))
            return
        self.snapshot = snapshot
        rows = [(os.path.join(plan.display_name, old),
                 os.path.join(plan.display_name, new))
                for plan in snapshot.plans for old, new in plan.mapping]
        self.table.setRowCount(len(rows))
        for row, (old, new) in enumerate(rows):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(old))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(new))
        self.rename_btn.setEnabled(True)
        self.logger.info("Preview ready: %d file(s) in %d folder(s).",
                         len(rows), len(snapshot.plans))
        for warning in snapshot.warnings:
            self.logger.warning(warning)

    def _rename(self) -> None:
        snapshot = self.snapshot
        if snapshot is None:
            return
        if not preview_is_current(snapshot, self.folder_edit.text(),
                                  self.auto_check.isChecked(), self.first_edit.text()):
            self._invalidate()
            self.table.setRowCount(0)
            QtWidgets.QMessageBox.warning(
                self, "Preview out of date",
                "The folders, files, or target input changed. Generate a new preview.")
            return
        count = sum(len(plan.mapping) for plan in snapshot.plans)
        if QtWidgets.QMessageBox.question(
                self, "Confirm rename", f"Rename {count} .hex file(s)?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        self._set_running(True)
        self.worker = RenameWorker(snapshot.plans, self)
        self.worker.progress.connect(self._progress)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _set_running(self, running: bool) -> None:
        for widget in (self.folder_edit, self.first_edit, self.auto_check,
                       self.browse_btn, self.preview_btn, self.rename_btn):
            widget.setEnabled(not running)
        if not running:
            self.first_edit.setEnabled(not self.auto_check.isChecked())
        self.cancel_btn.setEnabled(running)

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.logger.warning("Cancellation requested; current operation will roll back safely.")

    def _progress(self, step: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(step)
        self.progress.setFormat(f"{int(step * 100 / total) if total else 0}% ({step}/{total} steps)")

    def _completed(self, renamed: int, skipped: int, total: int) -> None:
        self.logger.info("Completed: %d renamed, %d unchanged.", renamed, skipped)
        QtWidgets.QMessageBox.information(
            self, "Rename complete",
            f"Renamed: {renamed}\nUnchanged: {skipped}\nTotal: {total}")
        self._finish_worker()

    def _failed(self, message: str) -> None:
        self.logger.error("Rename failed: %s", message)
        QtWidgets.QMessageBox.critical(self, "Rename failed", message)
        self._finish_worker()

    def _finish_worker(self) -> None:
        self._set_running(False)
        self.snapshot = None
        self.rename_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.progress.setValue(0)
        self.worker = None


class RenameMainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HEX File Rename Utility")
        self.setMinimumSize(900, 650)
        self.setCentralWidget(FileRenameWidget())
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f5f7fa; color: #17212b; }
            QGroupBox { font-weight: 600; border: 1px solid #cbd5e1;
                        border-radius: 7px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLineEdit, QPlainTextEdit, QTableWidget { background: white;
                        border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px; }
            QPushButton { background: #e2e8f0; border: 1px solid #cbd5e1;
                          border-radius: 5px; padding: 7px 12px; }
            QPushButton:hover { background: #d8e0ea; }
            QPushButton#primary { background: #1976d2; color: white; border-color: #1976d2; }
            QPushButton#primary:hover { background: #1565c0; }
            QPushButton:disabled { color: #94a3b8; background: #edf1f5; }
            QHeaderView::section { background: #e8eef5; padding: 6px; border: 0; }
        """)


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("HEX File Rename Utility")
    window = RenameMainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
