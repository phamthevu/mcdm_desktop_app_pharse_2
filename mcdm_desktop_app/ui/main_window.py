from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QDialog, QVBoxLayout, QTextEdit, QPushButton, QLabel,
)

from core.models import Expert, ProjectConfig, config_from_dict, config_to_dict
from core.project_db import ProjectDB
from ui.tab_config import TabConfig
from ui.tab_survey import TabSurvey
from ui.tab_data_manager import TabDataManager


class MainWindow(QMainWindow):
    """Application shell and project lifecycle manager."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCDM Decision Support System (Fuzzy & Z-Number)")
        self.resize(1200, 800)

        self.project_db = None
        self.project_path = None
        self.project_name = None

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_config = TabConfig()
        self.tab_survey = TabSurvey()
        self.tab_data = TabDataManager()
        self.tabs.addTab(self.tab_config, "1. Configuration")
        self.tabs.addTab(self.tab_survey, "2. Survey Matrix")
        self.tabs.addTab(self.tab_data, "3. Data Manager")
        self.tabs.setTabEnabled(1, False)
        self.tabs.setTabEnabled(2, False)
        self.tab_data.edit_response_requested.connect(self._edit_response_from_manager)
        self.tab_data.respondents_changed.connect(self._refresh_mutable_project_data)

        self.tab_config.project_created.connect(self.create_project)

        self._build_menu()
        self.statusBar().showMessage("Ready — create or open a project")
        self._update_window_state()

    # ------------------------------------------------------------------
    # Menu / project lifecycle
    # ------------------------------------------------------------------
    def _build_menu(self):
        file_menu = self.menuBar().addMenu("File")

        self.action_new = QAction("New Project", self)
        self.action_new.setShortcut("Ctrl+N")
        self.action_new.triggered.connect(self.new_project)
        file_menu.addAction(self.action_new)

        self.action_open = QAction("Open Project...", self)
        self.action_open.setShortcut("Ctrl+O")
        self.action_open.triggered.connect(self.open_project_dialog)
        file_menu.addAction(self.action_open)

        self.action_save = QAction("Save Project", self)
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self.save_project)
        file_menu.addAction(self.action_save)

        self.action_close = QAction("Close Project", self)
        self.action_close.setShortcut("Ctrl+W")
        self.action_close.triggered.connect(self.close_project)
        file_menu.addAction(self.action_close)

        file_menu.addSeparator()

        self.action_export = QAction("Export Results...", self)
        self.action_export.triggered.connect(self.export_results)
        file_menu.addAction(self.action_export)

        self.action_merge = QAction("Merge Projects...", self)
        self.action_merge.triggered.connect(self.merge_projects)
        file_menu.addAction(self.action_merge)

        self.action_info = QAction("Project Information...", self)
        self.action_info.triggered.connect(self.show_project_information)
        file_menu.addAction(self.action_info)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _update_window_state(self):
        opened = self.project_db is not None
        self.action_save.setEnabled(opened)
        self.action_close.setEnabled(opened)
        self.action_export.setEnabled(opened)
        self.action_merge.setEnabled(opened)
        self.action_info.setEnabled(opened)
        if opened:
            meta = self.project_db.get_meta()
            self.project_name = meta["project_name"] if meta else self.project_name
            self.setWindowTitle(
                f"MCDM Decision Support System — {self.project_name}"
            )
        else:
            self.setWindowTitle("MCDM Decision Support System (Fuzzy & Z-Number)")

    def new_project(self):
        if not self._close_current_if_needed():
            return
        self.tab_config = TabConfig()
        self.tab_config.project_created.connect(self.create_project)
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, self.tab_config, "1. Configuration")
        self.tabs.setCurrentIndex(0)
        self.tabs.setTabEnabled(1, False)
        self.tabs.setTabEnabled(2, False)
        self.tab_data.clear_project()
        self._update_window_state()

    def open_project_dialog(self):
        # Choose the target first. Cancelling the dialog must not close the
        # currently open project.
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MCDM Project",
            str(Path.home()),
            "MCDM Project (*.mcdm)",
        )
        if not path:
            return
        self.open_project(path)

    def create_project(self, config: ProjectConfig, db_path: str, project_name: str):
        try:
            ProjectDB.create_project(
                db_path=db_path,
                project_name=project_name,
                project_type="MCDM",
                config_dict=config_to_dict(config),
                accounts_list=[
                    {
                        "Respondent_ID": exp.respondent_id,
                        "Username": exp.username,
                        "Password": exp.password,
                        "Full_Name": exp.name,
                        "Organization": exp.organization,
                    }
                    for exp in config.experts
                ],
            )
            self.open_project(db_path, show_message=True)
        except Exception as exc:
            QMessageBox.critical(
                self, "Create Project Failed", f"Could not create project:\n\n{exc}"
            )

    def open_project(self, path: str, show_message: bool = False):
        try:
            db = ProjectDB(path)
            meta = db.get_meta()
            if not meta:
                raise ValueError("Project metadata is missing.")

            config = config_from_dict(db.get_config_dict())
            # Respondents are project data, not immutable config. Rebuild the
            # expert list from the database so added accounts are immediately usable.
            if config.expert_auth_mode == "Account":
                config.experts = [
                    Expert(
                        name=str(r.get("full_name", "")),
                        username=str(r.get("username", "")),
                        password=str(r.get("password", "")),
                        respondent_id=str(r.get("respondent_id", "")),
                        organization=str(r.get("organization", "")),
                    )
                    for r in db.get_respondents()
                ]

            if self.project_db:
                self.project_db.close()
            self.project_db = db
            self.project_path = str(Path(path).resolve())
            self.project_name = meta["project_name"]

            self.tab_config.load_locked_project(config)
            self.tab_survey.load_project(config, db)
            self.tab_data.load_project(db)
            self.tabs.setTabEnabled(1, True)
            self.tabs.setTabEnabled(2, True)
            self.tabs.setCurrentIndex(1)
            self._update_window_state()

            self.statusBar().showMessage(f"Opened: {self.project_name} — {self.project_path}", 8000)
            title = "Project Created" if show_message else "Project Opened"
            lead = "Project created and opened successfully." if show_message else "Project opened successfully."
            QMessageBox.information(
                self, title,
                f"{lead}\n\nProject: {self.project_name}\nFile: {self.project_path}"
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Open Project Failed", f"Could not open project:\n\n{exc}"
            )

    def save_project(self):
        if not self.project_db:
            return
        try:
            self.project_db.conn.commit()
            self._update_window_state()
            from datetime import datetime
            saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.statusBar().showMessage(f"Saved successfully at {saved_at}", 8000)
            QMessageBox.information(
                self, "Project Saved",
                f"Project saved successfully.\n\nProject: {self.project_name}\nFile: {self.project_path}\nSaved at: {saved_at}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def close_project(self):
        if self.project_db:
            answer = QMessageBox.question(
                self, "Close Project",
                f"Close project '{self.project_name}'?\n\nAll saved database changes are already persisted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if not self._close_current_if_needed(force=True):
            return
        self._reset_project_ui()

    def _close_current_if_needed(self, force: bool = False) -> bool:
        if not self.project_db:
            return True
        # Responses are persisted immediately on Save Evaluation, so there is
        # currently no unsaved database transaction to discard.
        if not force:
            self.project_db.conn.commit()
        else:
            self.project_db.conn.commit()
        self.project_db.close()
        self.project_db = None
        self.project_path = None
        self.project_name = None
        return True

    def _reset_project_ui(self):
        self.tabs.setTabEnabled(1, False)
        self.tabs.setTabEnabled(2, False)
        self.tab_data.clear_project()
        self.tabs.setCurrentIndex(0)
        self.tab_config = TabConfig()
        self.tab_config.project_created.connect(self.create_project)
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, self.tab_config, "1. Configuration")
        self._update_window_state()
        self.statusBar().showMessage("Project closed", 5000)

    def _refresh_mutable_project_data(self):
        if not self.project_db:
            return
        self.tab_survey.refresh_respondents_from_db()
        self.tab_data.refresh()

    def _edit_response_from_manager(self, respondent_id: str):
        self.tab_survey.open_response_for_edit(respondent_id)
        self.tabs.setCurrentWidget(self.tab_survey)

    # ------------------------------------------------------------------
    # Export / merge
    # ------------------------------------------------------------------
    def export_results(self):
        if not self.project_db:
            return
        self.tab_survey.on_export_all_clicked()

    def merge_projects(self):
        if not self.project_db:
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Projects to Merge",
            str(Path(self.project_path).parent if self.project_path else Path.home()),
            "MCDM Project (*.mcdm)",
        )
        if not paths:
            return

        compatible = []
        incompatible = []
        for path in paths:
            try:
                report = self.project_db.compare_merge_config(path)
                if report["compatible"]:
                    compatible.append(path)
                else:
                    details = "\n    ".join(report.get("differences") or ["Config hash differs."])
                    incompatible.append(f"{Path(path).name}\n    {details}")
            except Exception as exc:
                incompatible.append(f"{Path(path).name}: {exc}")

        if incompatible:
            QMessageBox.warning(
                self,
                "Merge Blocked",
                "The following projects do not have exactly the same configuration:\n\n"
                + "\n".join(incompatible),
            )
            if not compatible:
                return

        if not compatible:
            return

        answer = QMessageBox.question(
            self,
            "Confirm Merge",
            "Merge the compatible projects into the currently open project?\n\n"
            + "\n".join(Path(p).name for p in compatible),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            logs = self.project_db.merge_other_projects(compatible)
            self.tab_survey.reload_from_project_db()
            self.tab_data.refresh()
            summary = "\n".join(
                f"{item['project_name']}: {item['count']} response(s)"
                for item in logs
            )
            QMessageBox.information(
                self, "Merge Complete", f"Projects merged successfully.\n\n{summary}"
            )
            self.statusBar().showMessage("Merge completed successfully", 8000)
        except Exception as exc:
            QMessageBox.critical(self, "Merge Failed", str(exc))

    def show_project_information(self):
        if not self.project_db:
            return
        meta = self.project_db.get_meta() or {}
        respondents = self.project_db.get_respondents()
        responses = self.project_db.get_all_responses()
        history = self.project_db.get_merge_history()
        history_text = "\n".join(
            f"- {h.get('source_project_name')} | {h.get('imported_count')} response(s) | {h.get('merged_at')} | {h.get('source_file')}"
            for h in history
        ) or "No merge history."
        text = (
            f"Project Name: {meta.get('project_name', '')}\n"
            f"Project ID: {meta.get('project_id', '')}\n"
            f"Project Type: {meta.get('project_type', '')}\n"
            f"File: {self.project_path}\n"
            f"Created: {meta.get('created_at', '')}\n"
            f"Modified: {meta.get('modified_at', '')}\n"
            f"Config Hash: {meta.get('config_hash', '')}\n"
            f"Respondents: {len(respondents)}\n"
            f"Responses: {len(responses)}\n\n"
            f"MERGE HISTORY\n{history_text}"
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Project Information")
        dlg.resize(760, 520)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Project metadata and merge audit history"))
        box = QTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        layout.addWidget(box)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    def closeEvent(self, event):
        if self.project_db:
            self.project_db.close()
            self.project_db = None
        event.accept()
