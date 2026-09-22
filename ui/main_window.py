from pathlib import Path

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QFileDialog,
    QMessageBox,
)

from core.models import Expert, ProjectConfig, config_from_dict, config_to_dict
from core.project_db import ProjectDB
from ui.tab_config import TabConfig
from ui.tab_survey import TabSurvey


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
        self.tabs.addTab(self.tab_config, "1. Configuration")
        self.tabs.addTab(self.tab_survey, "2. Survey Matrix")
        self.tabs.setTabEnabled(1, False)

        self.tab_config.project_created.connect(self.create_project)

        self._build_menu()
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
            self.tabs.setTabEnabled(1, True)
            self.tabs.setCurrentIndex(1)
            self._update_window_state()

            if show_message:
                QMessageBox.information(
                    self,
                    "Project Created",
                    f"Project created successfully:\n\n{self.project_path}",
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
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))

    def close_project(self):
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
        self.tabs.setCurrentIndex(0)
        self.tab_config = TabConfig()
        self.tab_config.project_created.connect(self.create_project)
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, self.tab_config, "1. Configuration")
        self._update_window_state()

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
                if self.project_db.is_merge_compatible(path):
                    compatible.append(path)
                else:
                    incompatible.append(Path(path).name)
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
            summary = "\n".join(
                f"{item['project_name']}: {item['count']} response(s)"
                for item in logs
            )
            QMessageBox.information(
                self, "Merge Complete", f"Projects merged successfully.\n\n{summary}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Merge Failed", str(exc))

    def closeEvent(self, event):
        if self.project_db:
            self.project_db.close()
            self.project_db = None
        event.accept()
