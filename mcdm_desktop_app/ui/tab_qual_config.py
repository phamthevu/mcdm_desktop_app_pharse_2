from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QFileDialog,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QGroupBox,QFormLayout,QInputDialog
from core.qualitative_excel import parse_qualitative_excel,generate_qualitative_template,qualitative_config_to_dict
class TabQualConfig(QWidget):
    project_created=pyqtSignal(dict,list,str,str)
    def __init__(self):
        super().__init__(); self.questions=[]; self.accounts=[]; self.locked=False; lay=QVBoxLayout(self)
        t=QLabel("QUALITATIVE IN-DEPTH INTERVIEW CONFIGURATION"); t.setStyleSheet("font-size:16px;font-weight:bold"); lay.addWidget(t)
        n=QLabel("The initial interview guide is immutable after project creation. Follow-up question/answer pairs added during an interview are response data and do not change merge compatibility."); n.setWordWrap(True); lay.addWidget(n)
        row=QHBoxLayout(); self.path=QLineEdit(); self.path.setPlaceholderText("Interview guide .xlsx"); row.addWidget(self.path); b=QPushButton("Browse..."); b.clicked.connect(self.browse); row.addWidget(b); g=QPushButton("Generate Template..."); g.clicked.connect(self.gen); row.addWidget(g); lay.addLayout(row)
        box=QGroupBox("Participant Access (locked after project creation)"); f=QFormLayout(box); self.auth_mode=QComboBox(); self.auth_mode.addItem("Free / Anonymous","Free"); self.auth_mode.addItem("Account Required","Account"); f.addRow("Access mode",self.auth_mode); lay.addWidget(box)
        self.status=QLabel("Load an interview guide to validate it."); self.status.setWordWrap(True); lay.addWidget(self.status); self.table=QTableWidget(); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); lay.addWidget(self.table)
        self.create=QPushButton("CREATE QUALITATIVE INTERVIEW PROJECT"); self.create.setProperty("primary",True); self.create.setMinimumHeight(44); self.create.clicked.connect(self.create_project); lay.addWidget(self.create)
    def browse(self):
        p,_=QFileDialog.getOpenFileName(self,"Interview Guide","","Excel (*.xlsx *.xls)")
        if p:self.path.setText(p); self.load_preview()
    def gen(self):
        p,_=QFileDialog.getSaveFileName(self,"Save Interview Template","Qualitative_Interview_Template.xlsx","Excel (*.xlsx)")
        if not p:return
        if not p.lower().endswith('.xlsx'):p+='.xlsx'
        generate_qualitative_template(p); self.path.setText(p); self.load_preview(); QMessageBox.information(self,"Template Created",f"Interview template created successfully.\n\n{p}")
    def load_preview(self):
        try:
            self.questions,self.accounts=parse_qualitative_excel(self.path.text().strip()); self.table.setRowCount(len(self.questions)); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["ID","Initial Question","Required","Order"])
            for r,q in enumerate(self.questions):
                for c,v in enumerate([q['question_id'],q['question_text'],"Yes" if q['required'] else "No",q['display_order']]):self.table.setItem(r,c,QTableWidgetItem(str(v)))
            self.status.setText(f"Validated: {len(self.questions)} initial question(s), {len(self.accounts)} account(s).")
        except Exception as e:QMessageBox.critical(self,"Invalid Interview Guide",str(e))
    def create_project(self):
        if not self.questions:
            if not self.path.text().strip():QMessageBox.warning(self,"Missing Guide","Please load an interview guide first."); return
            self.load_preview()
            if not self.questions:return
        name,ok=QInputDialog.getText(self,"Project Name","Project name:")
        if not ok or not name.strip():return
        p,_=QFileDialog.getSaveFileName(self,"Save Project",name.strip()+".mcdm","Research Project (*.mcdm)")
        if not p:return
        if not p.lower().endswith('.mcdm'):p+='.mcdm'
        self.project_created.emit(qualitative_config_to_dict(self.questions,self.auth_mode.currentData()),self.accounts,p,name.strip())
    def load_locked_project(self,config):
        self.locked=True; self.questions=config.get('initial_questions',[]); self.path.setText("Configuration stored inside project (locked)"); self.path.setEnabled(False); self.auth_mode.setCurrentIndex(max(0,self.auth_mode.findData(config.get('auth_mode','Free')))); self.auth_mode.setEnabled(False); self.create.setEnabled(False); self.table.setRowCount(len(self.questions)); self.table.setColumnCount(4); self.table.setHorizontalHeaderLabels(["ID","Initial Question","Required","Order"])
        for r,q in enumerate(self.questions):
            for c,v in enumerate([q.get('question_id'),q.get('question_text'),"Yes" if q.get('required') else "No",q.get('display_order')]):self.table.setItem(r,c,QTableWidgetItem(str(v)))
        self.status.setText("Configuration locked. Only the initial interview guide defines merge compatibility.")
