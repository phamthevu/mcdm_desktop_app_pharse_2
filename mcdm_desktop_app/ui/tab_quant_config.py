from pathlib import Path
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QInputDialog
from core.survey_excel import parse_survey_excel, generate_survey_template
from core.survey_models import survey_config_to_dict

class TabQuantConfig(QWidget):
    project_created = pyqtSignal(dict, list, str, str)
    def __init__(self):
        super().__init__(); self.questions=[]; self.accounts=[]; self.locked=False
        lay=QVBoxLayout(self); title=QLabel("QUANTITATIVE SURVEY CONFIGURATION"); title.setStyleSheet("font-size:16px;font-weight:bold"); lay.addWidget(title)
        row=QHBoxLayout(); self.path=QLineEdit(); self.path.setPlaceholderText("Survey configuration .xlsx"); row.addWidget(self.path)
        b=QPushButton("Browse..."); b.clicked.connect(self.browse); row.addWidget(b); g=QPushButton("Generate Template..."); g.clicked.connect(self.gen); row.addWidget(g); lay.addLayout(row)
        self.info=QLabel("Questions sheet defines the immutable survey schema. Accounts remain mutable after project creation."); lay.addWidget(self.info)
        self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); lay.addWidget(self.table)
        self.create=QPushButton("CREATE QUANTITATIVE SURVEY PROJECT"); self.create.setMinimumHeight(44); self.create.clicked.connect(self.create_project); lay.addWidget(self.create)
    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,"Survey Config","","Excel (*.xlsx *.xls)")
        if p: self.path.setText(p); self.load_preview()
    def gen(self):
        p,_=QFileDialog.getSaveFileName(self,"Save Survey Template","Survey_Config_Template.xlsx","Excel (*.xlsx)")
        if p:
            if not p.lower().endswith('.xlsx'): p += '.xlsx'
            generate_survey_template(p); self.path.setText(p); self.load_preview(); QMessageBox.information(self,"Template Created",f"Survey template created successfully.\n\n{p}")
    def load_preview(self):
        try:
            self.questions,self.accounts=parse_survey_excel(self.path.text().strip())
            self.table.setRowCount(len(self.questions)); self.table.setColumnCount(6); self.table.setHorizontalHeaderLabels(["ID","Question","Type","Required","Options","Range"])
            for r,q in enumerate(self.questions):
                vals=[q.question_id,q.question_text,q.question_type,"Yes" if q.required else "No",q.options,f"{q.min_value or ''} .. {q.max_value or ''}"]
                for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))
            self.info.setText(f"Validated: {len(self.questions)} question/layout item(s), {len(self.accounts)} account(s).")
        except Exception as e: QMessageBox.critical(self,"Invalid Survey Config",str(e))
    def create_project(self):
        if not self.questions: self.load_preview()
        if not self.questions: return
        name,ok=QInputDialog.getText(self,"Project Name","Project name:")
        if not ok or not name.strip(): return
        p,_=QFileDialog.getSaveFileName(self,"Save Project",name.strip()+".mcdm","MCDM Project (*.mcdm)")
        if not p:return
        if not p.lower().endswith('.mcdm'):p += '.mcdm'
        self.project_created.emit(survey_config_to_dict(self.questions),self.accounts,p,name.strip())
    def load_locked_project(self, config):
        self.locked=True; self.questions=[]; self.accounts=[]; self.path.setText("Configuration stored inside project (LOCKED)"); self.path.setEnabled(False); self.create.setEnabled(False)
        qs=config.get("questions",[]); self.table.setRowCount(len(qs)); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["ID","Question","Type","Required"])
        for r,q in enumerate(qs):
            for c,v in enumerate([q.get('question_id'),q.get('question_text'),q.get('question_type'),q.get('required')]): self.table.setItem(r,c,QTableWidgetItem(str(v)))
        self.info.setText("🔒 Configuration locked. Question definitions cannot be changed for this project.")
