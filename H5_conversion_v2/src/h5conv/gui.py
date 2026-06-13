"""PySide6 GUI for the H5 conversion tool.

A single window. Layouts (no absolute geometry). All long-running work
runs in a `QThread` so the UI stays responsive. Cross-platform; tested
on macOS and Windows.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from h5conv.core import (
    ConvertConfig,
    ConvertStats,
    DEFAULT_DEAD_PIXELS,
    DEFAULT_DATASET_KEY,
    convert_directory,
    load_flatfield,
    parse_dead_pixels,
)


os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(os.getenv("TMPDIR", "/tmp")) / "h5conv-mpl")
)


# ---------------------------------------------------------------------------
# Colormap catalog.
#
# Curated subsets of matplotlib's colormap library, grouped by the standard
# perceptual-family taxonomy (sequential, diverging, cyclic, qualitative,
# miscellaneous). Names are those returned by `matplotlib.colormaps`; the GUI
# does case-folding at lookup time.
# ---------------------------------------------------------------------------

COLORMAP_CATEGORIES: dict[str, list[str]] = {
    "Sequential": [
        "gray", "gray_r",
        "viridis", "plasma", "inferno", "magma", "cividis",
        "Blues", "Greens", "Oranges", "Reds", "Purples",
        "YlOrBr", "YlOrRd", "OrRd", "BuPu", "GnBu",
        "bone", "afmhot", "hot", "gist_heat", "copper",
    ],
    "Diverging": [
        "RdBu", "RdBu_r", "RdGy", "RdGy_r",
        "BrBG", "BrBG_r", "PiYG", "PiYG_r",
        "PRGn", "PRGn_r", "PuOr", "PuOr_r",
        "RdYlBu", "RdYlBu_r", "RdYlGn", "RdYlGn_r",
        "Spectral", "Spectral_r",
        "coolwarm", "bwr", "seismic",
    ],
    "Cyclic": [
        "twilight", "twilight_shifted", "hsv",
    ],
    "Qualitative": [
        "tab10", "tab20", "tab20b", "tab20c",
        "Set1", "Set2", "Set3", "Pastel1", "Pastel2", "Paired",
        "Accent", "Dark2",
    ],
    "Miscellaneous": [
        "jet", "jet_r", "turbo", "rainbow", "nipy_spectral",
        "gist_earth", "gist_gray", "gist_stern", "gist_ncar",
        "terrain", "ocean", "flag", "prism", "CMRmap",
    ],
}


# ---------------------------------------------------------------------------
# Worker that runs convert_directory in a background thread.
# ---------------------------------------------------------------------------


class _ConversionWorker(QObject):
    progress = Signal(int, int, str)   # frame_index, total, message
    finished = Signal(object)          # ConvertStats
    failed = Signal(str)

    def __init__(self, config: ConvertConfig):
        super().__init__()
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _is_cancelled(self) -> bool:
        return self._cancelled

    def _emit(self, frame_idx: int, total: int, msg: str) -> None:
        self.progress.emit(frame_idx, total, msg)

    def run(self) -> None:
        try:
            stats = convert_directory(
                self._config,
                progress=self._emit,
                is_cancelled=self._is_cancelled,
            )
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{exc}\n{traceback.format_exc()}")
            return
        self.finished.emit(stats)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("H5 Conversion")
        self.resize(980, 700)

        self._flatfield: np.ndarray | None = None
        self._thread: QThread | None = None
        self._worker: _ConversionWorker | None = None
        self._running = False
        self._config_widgets: list[QWidget] = []

        self._build_ui()

    # ----- UI construction ------------------------------------------------

    def _tracked(self, widget):
        self._config_widgets.append(widget)
        return widget

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(self._build_io_group())
        left.addWidget(self._build_options_group())
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._build_advanced_group())
        right.addWidget(self._build_actions_group())
        right.addWidget(self._build_log_group(), stretch=1)

        columns.addLayout(left, stretch=3)
        columns.addLayout(right, stretch=2)
        root.addLayout(columns, stretch=1)

    def _build_io_group(self) -> QGroupBox:
        box = QGroupBox("Input / Output")
        grid = QGridLayout(box)
        grid.setColumnStretch(1, 1)

        self.input_edit = self._tracked(QLineEdit())
        self.input_edit.setPlaceholderText("Folder containing *.h5 master files")
        input_btn = self._tracked(QPushButton("Browse..."))
        input_btn.clicked.connect(self._pick_input)

        self.output_edit = self._tracked(QLineEdit())
        self.output_edit.setPlaceholderText("Folder to write .npy / .tiff / .tif")
        output_btn = self._tracked(QPushButton("Browse..."))
        output_btn.clicked.connect(self._pick_output)

        self.flatfield_edit = self._tracked(QLineEdit())
        self.flatfield_edit.setPlaceholderText(
            "Optional: 512x512 flatfield .npy / .tif"
        )
        ff_browse = self._tracked(QPushButton("Browse..."))
        ff_browse.clicked.connect(self._pick_flatfield)
        ff_clear = self._tracked(QPushButton("Clear"))
        ff_clear.clicked.connect(self._clear_flatfield)

        ff_row = QHBoxLayout()
        ff_row.addWidget(self.flatfield_edit, stretch=1)
        ff_row.addWidget(ff_browse)
        ff_row.addWidget(ff_clear)

        grid.addWidget(QLabel("Input folder:"), 0, 0)
        grid.addWidget(self.input_edit, 0, 1)
        grid.addWidget(input_btn, 0, 2)
        grid.addWidget(QLabel("Output folder:"), 1, 0)
        grid.addWidget(self.output_edit, 1, 1)
        grid.addWidget(output_btn, 1, 2)
        grid.addWidget(QLabel("Flatfield:"), 2, 0)
        grid.addLayout(ff_row, 2, 1, 1, 2)
        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("Processing options")
        form = QFormLayout(box)
        form.setLabelAlignment(form.labelAlignment())

        self.apply_ff_check = self._tracked(QCheckBox("Apply flatfield (multiply)"))
        self.apply_ff_check.setChecked(False)
        self.apply_ff_check.toggled.connect(self._refresh_apply_ff_state)

        self.fix_dead_check = self._tracked(QCheckBox("Fix known dead pixels"))
        self.fix_dead_check.setChecked(True)

        self.min_pct = self._tracked(QDoubleSpinBox())
        self.min_pct.setRange(0.0, 100.0)
        self.min_pct.setDecimals(2)
        self.min_pct.setValue(1.0)
        self.min_pct.setSingleStep(0.1)

        self.max_pct = self._tracked(QDoubleSpinBox())
        self.max_pct.setRange(0.0, 100.0)
        self.max_pct.setDecimals(2)
        self.max_pct.setValue(99.0)
        self.max_pct.setSingleStep(0.1)

        self.save_npy = self._tracked(QCheckBox(".npy raw float32"))
        self.save_npy.setChecked(True)
        self.save_tiff = self._tracked(QCheckBox(".tiff raw float32"))
        self.save_tiff.setChecked(True)
        self.save_tif = self._tracked(QCheckBox(".tif display image"))
        self.save_tif.setChecked(True)

        self.cmap_category = self._tracked(QComboBox())
        # Categories must match the keys in COLORMAP_CATEGORIES below.
        self.cmap_category.addItems(list(COLORMAP_CATEGORIES.keys()))
        self.cmap_category.setCurrentText("Sequential")
        # Color chip on the right side of the colormap dropdown, showing
        # the currently selected colormap as a small horizontal gradient.
        self.cmap_swatch_small = QLabel()
        self.cmap_swatch_small.setFixedSize(140, 20)
        self.cmap_swatch_small.setFrameShape(QLabel.Box)
        self.cmap_swatch_small.setLineWidth(1)
        self.cmap_swatch_small.setStyleSheet(
            "QLabel { background-color: #ddd; border: 1px solid #888; }"
        )
        self.cmap_swatch_small.setScaledContents(True)

        self.cmap_combo = self._tracked(QComboBox())
        self._populate_cmap_combo("Sequential", default="gray")
        cmap_row = QHBoxLayout()
        cmap_row.setContentsMargins(0, 0, 0, 0)
        cmap_row.setSpacing(8)
        cmap_row.addWidget(self.cmap_combo)
        cmap_row.addWidget(self.cmap_swatch_small)
        cmap_row.addStretch(1)
        cmap_row_holder = QWidget()
        cmap_row_holder.setLayout(cmap_row)

        save_box = QGridLayout()
        save_box.setContentsMargins(0, 0, 0, 0)
        save_box.addWidget(self.save_npy, 0, 0)
        save_box.addWidget(self.save_tiff, 0, 1)
        save_box.addWidget(self.save_tif, 1, 0, 1, 2)
        save_holder = QWidget()
        save_holder.setLayout(save_box)

        # Dead-pixel positions, in case the user wants to override
        self.dead_pixels_edit = self._tracked(
            QLineEdit("; ".join(f"{r},{c}" for r, c in DEFAULT_DEAD_PIXELS))
        )
        self.dead_pixels_edit.setPlaceholderText("row,col pairs e.g. 164,87; 192,85")

        form.addRow("", self.apply_ff_check)
        form.addRow("", self.fix_dead_check)
        form.addRow("Min percentile (for .tif):", self.min_pct)
        form.addRow("Max percentile (for .tif):", self.max_pct)
        form.addRow("Colormap category:", self.cmap_category)
        form.addRow("Colormap (.tif):", cmap_row_holder)
        form.addRow("Save formats:", save_holder)
        form.addRow("Dead pixels (r,c;…):", self.dead_pixels_edit)

        # Wire the colormap preview: repaint the chip on every selection change.
        self.cmap_combo.currentTextChanged.connect(self._refresh_cmap_swatches)
        # Changing category repopulates the cmap dropdown. We try to keep
        # the current selection if it exists in the new category; otherwise
        # we fall back to the category's first entry.
        self.cmap_category.currentTextChanged.connect(self._on_category_changed)
        self._refresh_cmap_swatches(self.cmap_combo.currentText())

        self._refresh_apply_ff_state()
        return box

    def _build_advanced_group(self) -> QGroupBox:
        box = QGroupBox("Advanced")
        form = QFormLayout(box)

        self.file_keyword_edit = self._tracked(QLineEdit("master"))
        self.file_keyword_edit.setPlaceholderText("Empty converts every .h5 file")

        self.dataset_key_edit = self._tracked(QLineEdit(DEFAULT_DATASET_KEY))
        self.dataset_key_edit.setPlaceholderText("Fallback uses first dataset under entry/data")

        self.overwrite_check = self._tracked(QCheckBox("Overwrite existing outputs"))
        self.overwrite_check.setChecked(True)

        form.addRow("File keyword:", self.file_keyword_edit)
        form.addRow("Dataset key:", self.dataset_key_edit)
        form.addRow("", self.overwrite_check)
        return box

    def _build_actions_group(self) -> QGroupBox:
        box = QGroupBox("Run")
        layout = QVBoxLayout(box)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Idle")
        self.progress.setTextVisible(True)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet("color: #555;")

        btn_row = QHBoxLayout()
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.setDefault(True)
        self.convert_btn.clicked.connect(self._start_conversion)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_conversion)
        btn_row.addStretch(1)
        btn_row.addWidget(self.convert_btn)
        btn_row.addWidget(self.cancel_btn)

        layout.addWidget(self.progress)
        layout.addWidget(self.status_label)
        layout.addLayout(btn_row)
        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Per-file progress appears here…")
        layout.addWidget(self.log)
        return box

    # ----- State helpers --------------------------------------------------

    def _refresh_apply_ff_state(self) -> None:
        self.apply_ff_check.setEnabled(
            self._flatfield is not None and not self._running
        )
        if self._flatfield is None:
            self.apply_ff_check.setChecked(False)
            self.apply_ff_check.setText(
                "Apply flatfield (multiply) - load a flatfield first"
            )
        else:
            self.apply_ff_check.setText(
                f"Apply flatfield (multiply) - shape {self._flatfield.shape}"
            )

    def _build_cmap_pixmap(self, name: str, width: int, height: int) -> QPixmap | None:
        """Render a horizontal gradient pixmap from a matplotlib colormap.

        Returns `None` (and the caller hides the swatch) if `name` is empty
        or refers to a missing colormap.
        """
        if not name:
            return None
        try:
            import matplotlib as mpl

            try:
                cmap_obj = mpl.colormaps[name]
            except (KeyError, ValueError):
                cmap_obj = mpl.colormaps["gray"]
        except Exception:  # noqa: BLE001 - matplotlib lookup can fail in odd envs
            return None
        # Sample the colormap along the width, then tile the 1×W row across
        # all `height` rows. Must be a *contiguous* (H, W, 3) uint8 array
        # because QImage does not own the numpy buffer — if the buffer is
        # the wrong shape (e.g. 1×W from a 1-D sample), Qt reads past the end
        # and the swatch paints noise.
        sample = np.linspace(0.0, 1.0, num=max(width, 2), dtype=np.float32)
        rgba = cmap_obj(sample)
        row = (rgba[..., :3] * 255.0).astype(np.uint8)        # shape (W, 3)
        rgb = np.tile(row[np.newaxis, :, :], (height, 1, 1))  # shape (H, W, 3)
        assert rgb.flags["C_CONTIGUOUS"], "rgb must be C-contiguous for QImage"
        qimg = QImage(
            rgb.data, width, height, 3 * width, QImage.Format_RGB888
        ).copy()
        return QPixmap.fromImage(qimg)

    def _populate_cmap_combo(self, category: str, default: str | None = None) -> None:
        """Refill the cmap dropdown with the entries from `category`.

        Names that aren't installed in this matplotlib build are filtered
        out, so the dropdown only ever shows colormaps we can actually
        render. `default` (if given) is preferred; otherwise the first
        available entry is selected.
        """
        names = COLORMAP_CATEGORIES.get(category, [])
        try:
            import matplotlib as mpl
            available = set(mpl.colormaps)
        except Exception:  # noqa: BLE001
            available = set(names)
        filtered = [n for n in names if n in available]
        if not filtered:
            filtered = ["gray"]

        previous = self.cmap_combo.blockSignals(True)  # avoid recursive refresh
        try:
            self.cmap_combo.clear()
            self.cmap_combo.addItems(filtered)
            target = default if default in filtered else filtered[0]
            self.cmap_combo.setCurrentText(target)
        finally:
            self.cmap_combo.blockSignals(previous)

    def _on_category_changed(self, category: str) -> None:
        # Try to keep the user's current selection when switching categories.
        self._populate_cmap_combo(category, default=self.cmap_combo.currentText())
        # Manually trigger a repaint (we blocked signals during refill).
        self._refresh_cmap_swatches(self.cmap_combo.currentText())

    def _refresh_cmap_swatches(self, name: str) -> None:
        small = self._build_cmap_pixmap(name, 140, 20)
        if small is None:
            self.cmap_swatch_small.clear()
            return
        self.cmap_swatch_small.setPixmap(small)

    def _log(self, message: str) -> None:
        self.log.append(message)

    # ----- File pickers ---------------------------------------------------

    def _pick_input(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select input folder")
        if path:
            self.input_edit.setText(path)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.output_edit.setText(path)

    def _pick_flatfield(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select flatfield",
            "",
            "Flatfield files (*.npy *.tif *.tiff);;All files (*)",
        )
        if not path:
            return
        try:
            self._flatfield = load_flatfield(Path(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Flatfield error", str(exc))
            self._flatfield = None
            self.flatfield_edit.clear()
        else:
            self.flatfield_edit.setText(path)
            self.apply_ff_check.setChecked(True)
        self._refresh_apply_ff_state()

    def _clear_flatfield(self) -> None:
        self._flatfield = None
        self.flatfield_edit.clear()
        self._refresh_apply_ff_state()

    # ----- Conversion lifecycle ------------------------------------------

    def _parse_dead_pixels(self) -> tuple[tuple[int, int], ...]:
        return parse_dead_pixels(self.dead_pixels_edit.text())

    def _validate(self) -> ConvertConfig | None:
        input_text = self.input_edit.text().strip()
        output_text = self.output_edit.text().strip()
        in_dir = Path(input_text)
        out_dir = Path(output_text)
        if not in_dir.is_dir():
            QMessageBox.warning(self, "Input folder", "Please choose a valid input folder.")
            return None
        if not output_text:
            QMessageBox.warning(self, "Output folder", "Please choose an output folder.")
            return None
        if self.min_pct.value() >= self.max_pct.value():
            QMessageBox.warning(
                self, "Percentiles", "Min percentile must be strictly less than max."
            )
            return None
        if not (self.save_npy.isChecked() or self.save_tiff.isChecked() or self.save_tif.isChecked()):
            QMessageBox.warning(self, "Outputs", "Select at least one save format.")
            return None
        file_keyword = self.file_keyword_edit.text().strip()
        dataset_key = self.dataset_key_edit.text().strip() or DEFAULT_DATASET_KEY
        try:
            dead = self._parse_dead_pixels()
        except ValueError as exc:
            QMessageBox.warning(self, "Dead pixels", str(exc))
            return None

        if self.apply_ff_check.isChecked() and self._flatfield is None:
            QMessageBox.warning(self, "Flatfield", "Load a flatfield first or uncheck the option.")
            return None

        return ConvertConfig(
            input_dir=in_dir,
            output_dir=out_dir,
            flatfield=self._flatfield if self.apply_ff_check.isChecked() else None,
            dead_pixels=dead,
            fix_dead_pixels=self.fix_dead_check.isChecked(),
            save_npy=self.save_npy.isChecked(),
            save_tiff=self.save_tiff.isChecked(),
            save_tif=self.save_tif.isChecked(),
            cmap=self.cmap_combo.currentText(),
            min_percentile=self.min_pct.value(),
            max_percentile=self.max_pct.value(),
            dataset_key=dataset_key,
            file_keyword=file_keyword,
            overwrite_existing=self.overwrite_check.isChecked(),
        )

    def _start_conversion(self) -> None:
        config = self._validate()
        if config is None:
            return
        if self._thread is not None:
            return  # already running

        self.log.clear()
        self._log(f"Output -> {config.output_dir}")
        self._log(
            f"Input: {config.input_dir} | keyword: {config.file_keyword or '(all .h5)'}"
        )
        self._log(f"Dataset key: {config.dataset_key}")
        if config.flatfield is not None:
            self._log(f"Flatfield applied: shape {config.flatfield.shape}")
        else:
            self._log("Flatfield: not applied")
        self._log(
            f"Save formats: "
            f"{'npy ' if config.save_npy else ''}"
            f"{'tiff ' if config.save_tiff else ''}"
            f"{'tif' if config.save_tif else ''}".strip()
        )
        self._log(f"Overwrite existing: {'yes' if config.overwrite_existing else 'no'}")

        self._set_running(True)

        self._thread = QThread(self)
        self._worker = _ConversionWorker(config)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def _cancel_conversion(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self._log("Cancellation requested...")
            self.cancel_btn.setEnabled(False)

    def _on_progress(self, completed: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(completed)
            self.progress.setFormat(f"%v / %m frames - {message}")
        else:
            # No file count could be pre-scanned; fall back to a static label.
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.progress.setFormat(f"Converting: {message}")
        self.status_label.setText(message)
        self._log(message)

    def _on_finished(self, stats: ConvertStats) -> None:
        self._set_running(False)
        self._show_final_progress(stats)
        if stats.cancelled:
            self._log(self._format_summary(stats, "Cancelled"))
            self.status_label.setText("Cancelled.")
        else:
            self._log(self._format_summary(stats, "Done"))
            self.status_label.setText("Done.")
            for err in stats.errors:
                self._log(f"ERROR: {err}")
            if stats.errors:
                QMessageBox.warning(
                    self,
                    "Conversion finished with errors",
                    "\n".join(stats.errors) or "Unknown error",
                )
            elif stats.files_total == 0:
                QMessageBox.information(
                    self,
                    "Conversion",
                    "No matching .h5 files were found.",
                )
            else:
                QMessageBox.information(self, "Conversion", "All files converted.")

    def _on_failed(self, message: str) -> None:
        self._set_running(False)
        self._log(f"FAILED: {message}")
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Conversion failed", message)

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        if self._worker is not None:
            self._worker.deleteLater()
        self._thread = None
        self._worker = None

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.convert_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        for w in self._config_widgets:
            w.setEnabled(not running)
        self._refresh_apply_ff_state()
        if running:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.progress.setFormat("Starting...")
            self.status_label.setText("Running...")

    def _show_final_progress(self, stats: ConvertStats) -> None:
        total = stats.frames_done + stats.frames_skipped
        if stats.files_total == 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.progress.setFormat("No matching files")
            return
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(total)
        if stats.cancelled:
            self.progress.setFormat(f"Cancelled - {total} frames handled")
        else:
            self.progress.setFormat(f"Done - {total} frames handled")

    def _format_summary(self, stats: ConvertStats, label: str) -> str:
        return (
            f"{label}. Files: {stats.files_done}/{stats.files_total}; "
            f"frames written: {stats.frames_done}; "
            f"frames skipped: {stats.frames_skipped}; "
            f"outputs written: {stats.outputs_written}; "
            f"outputs skipped: {stats.outputs_skipped}."
        )

    # ----- Shutdown -------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self._thread is not None and self._thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Conversion in progress",
                "A conversion is running. Cancel and quit?",
            )
            if reply != QMessageBox.Yes:
                event.ignore()
                return
            self._cancel_conversion()
            self._thread.quit()
            self._thread.wait(2000)
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("H5 Conversion")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
