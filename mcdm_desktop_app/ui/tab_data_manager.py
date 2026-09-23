import pandas as pd
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QFileDialog, QDialog, QFormLayout,
    QLineEdit, QDialogButtonBox, QLabel
)


class RespondentDialog(QDialog):
    def __init__(self, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle("Respondent")
        data = data or {}
        layout = QFormLayout(self)
        self.full_name = QLineEdit(str(data.get("full_name", "")))
        self.username = QLineEdit(str(data.get("username", "")))
        self.password = QLineEdit("" if data.get("respondent_id") else "123"); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.password.setPlaceholderText("Leave blank to keep current password" if data.get("respondent_id") else "Password")
        self.organization = QLineEdit(str(data.get("organization", "")))
        layout.addRow("Full name", self.full_name)
        layout.addRow("Username *", self.username)
        layout.addRow("Password", self.password)
        layout.addRow("Organization", self.organization)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        return {
            "full_name": self.full_name.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
            "organization": self.organization.text().strip(),
        }


class TabDataManager(QWidget):
    edit_response_requested = pyqtSignal(str)
    respondents_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_db = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        note = QLabel("Respondents are mutable project data. The research configuration remains locked.")
        note.setStyleSheet("font-weight:bold; color:#495057; padding:6px;")
        root.addWidget(note)

        grp_r = QGroupBox("Respondents / Expert Accounts")
        lr = QVBoxLayout(grp_r)
        bar = QHBoxLayout()
        for text, fn in [
            ("+ Add", self.add_respondent), ("Edit", self.edit_respondent),
            ("Delete", self.delete_respondent), ("Import Accounts Excel", self.import_accounts),
            ("Refresh", self.refresh),
        ]:
            b = QPushButton(text); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch(); lr.addLayout(bar)
        self.tbl_respondents = QTableWidget(0, 6)
        self.tbl_respondents.setHorizontalHeaderLabels(["Respondent ID", "Full Name", "Username", "Organization", "Status", "Created At"])
        self.tbl_respondents.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_respondents.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_respondents.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lr.addWidget(self.tbl_respondents)
        root.addWidget(grp_r, 1)

        grp_a = QGroupBox("Saved Responses / Interviews")
        la = QVBoxLayout(grp_a)
        abar = QHBoxLayout()
        b_edit = QPushButton("Open / Edit Response"); b_edit.clicked.connect(self.edit_response)
        b_del = QPushButton("Delete Response"); b_del.clicked.connect(self.delete_response)
        b_ref = QPushButton("Refresh"); b_ref.clicked.connect(self.refresh)
        abar.addWidget(b_edit); abar.addWidget(b_del); abar.addWidget(b_ref); abar.addStretch(); la.addLayout(abar)
        self.tbl_responses = QTableWidget(0, 8)
        self.tbl_responses.setHorizontalHeaderLabels(["Answer", "Expert", "Respondent ID", "Source Project", "Submitted At", "Merged At", "Source File", "DB ID"])
        self.tbl_responses.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_responses.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_responses.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        la.addWidget(self.tbl_responses)
        root.addWidget(grp_a, 1)

    def load_project(self, project_db):
        self.project_db = project_db
        self.refresh()

    def clear_project(self):
        self.project_db = None
        self.tbl_respondents.setRowCount(0); self.tbl_responses.setRowCount(0)

    def refresh(self):
        if not self.project_db: return
        respondents = self.project_db.get_respondents()
        self.tbl_respondents.setRowCount(len(respondents))
        for i, r in enumerate(respondents):
            vals = [r.get("respondent_id"), r.get("full_name"), r.get("username"), r.get("organization"), r.get("status"), r.get("created_at")]
            for j, v in enumerate(vals): self.tbl_respondents.setItem(i, j, QTableWidgetItem(str(v or "")))
        responses = self.project_db.get_all_responses()
        self.tbl_responses.setRowCount(len(responses))
        for i, r in enumerate(responses):
            vals = [f"Ans_{int(r['display_index']):02d}", r.get("full_name"), r.get("respondent_id"), r.get("source_project_name"), r.get("submitted_at"), r.get("merged_at"), r.get("source_file"), r.get("id")]
            for j, v in enumerate(vals): self.tbl_responses.setItem(i, j, QTableWidgetItem(str(v or "")))

    def _selected_respondent(self):
        row = self.tbl_respondents.currentRow()
        return self.tbl_respondents.item(row, 0).text() if row >= 0 else None

    def add_respondent(self):
        if not self.project_db: return
        d = RespondentDialog(self)
        if d.exec() != QDialog.DialogCode.Accepted: return
        v=d.values()
        try:
            self.project_db.add_respondent(**v); self.refresh(); self.respondents_changed.emit()
        except Exception as e: QMessageBox.critical(self, "Add Respondent", str(e))

    def edit_respondent(self):
        rid=self._selected_respondent()
        if not rid: return
        data=next((x for x in self.project_db.get_respondents() if x['respondent_id']==rid), None)
        d=RespondentDialog(self, data)
        if d.exec() != QDialog.DialogCode.Accepted: return
        try:
            self.project_db.update_respondent(rid, **d.values()); self.refresh(); self.respondents_changed.emit()
        except Exception as e: QMessageBox.critical(self, "Edit Respondent", str(e))

    def delete_respondent(self):
        rid=self._selected_respondent()
        if not rid: return
        if QMessageBox.question(self, "Delete Respondent", "Delete the selected respondent account?") != QMessageBox.StandardButton.Yes: return
        try:
            self.project_db.delete_respondent(rid); self.refresh(); self.respondents_changed.emit()
        except Exception as e: QMessageBox.warning(self, "Delete Respondent", str(e))

    def import_accounts(self):
        if not self.project_db: return
        path,_=QFileDialog.getOpenFileName(self,"Import Accounts", "", "Excel (*.xlsx *.xls)")
        if not path: return
        try:
            xls=pd.ExcelFile(path)
            sheet="Experts" if "Experts" in xls.sheet_names else ("Accounts" if "Accounts" in xls.sheet_names else None)
            if not sheet: raise ValueError("Excel must contain an 'Experts' or 'Accounts' sheet.")
            df=pd.read_excel(path, sheet_name=sheet).fillna("")
            accounts=[]
            for _,row in df.iterrows():
                accounts.append({
                    "Respondent_ID": row.get("Respondent_ID", ""),
                    "Username": row.get("Username", row.iloc[1] if len(row)>1 else ""),
                    "Password": row.get("Password", row.iloc[2] if len(row)>2 else "123"),
                    "Full_Name": row.get("Full_Name", row.get("Expert_Name", row.iloc[0] if len(row)>0 else "")),
                    "Organization": row.get("Organization", ""),
                })
            added=self.project_db.append_accounts(accounts); self.refresh(); self.respondents_changed.emit()
            QMessageBox.information(self,"Import Accounts",f"Added {added} new respondent(s). Existing IDs/usernames were skipped.")
        except Exception as e: QMessageBox.critical(self,"Import Accounts",str(e))

    def _selected_response(self):
        row=self.tbl_responses.currentRow()
        if row < 0: return None, None
        return int(self.tbl_responses.item(row,7).text()), self.tbl_responses.item(row,2).text()

    def edit_response(self):
        _,rid=self._selected_response()
        if rid: self.edit_response_requested.emit(rid)

    def delete_response(self):
        response_id,_=self._selected_response()
        if response_id is None: return
        if QMessageBox.question(self,"Delete Response","Delete this saved response/interview? This cannot be undone.") != QMessageBox.StandardButton.Yes: return
        self.project_db.delete_response(response_id); self.refresh(); self.respondents_changed.emit()
