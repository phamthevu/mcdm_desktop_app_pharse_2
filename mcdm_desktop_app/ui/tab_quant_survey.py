import json,re
from datetime import datetime
from PyQt6.QtCore import QDate,QTime,QDateTime
from PyQt6.QtWidgets import *
from openpyxl import Workbook

LAYOUT={"TITLE","SECTION","DESCRIPTION"}
class TabQuantSurvey(QWidget):
    def __init__(self): super().__init__(); self.db=None; self.config={}; self.widgets={}; self.build_shell()
    def build_shell(self):
        self.root=QVBoxLayout(self); top=QHBoxLayout(); top.addWidget(QLabel("Respondent:")); self.respondent=QComboBox(); top.addWidget(self.respondent,1); self.root.addLayout(top)
        self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.formhost=QWidget(); self.form=QVBoxLayout(self.formhost); self.scroll.setWidget(self.formhost); self.root.addWidget(self.scroll,1)
        row=QHBoxLayout(); self.save=QPushButton("SAVE RESPONSE"); self.save.clicked.connect(self.save_response); ex=QPushButton("Export Survey Data..."); ex.clicked.connect(self.export); row.addWidget(self.save); row.addWidget(ex); self.root.addLayout(row)
    def load_project(self, config, db): self.config=config; self.db=db; self.rebuild(); self.refresh_respondents_from_db()
    def reload_from_project_db(self): self.refresh_respondents_from_db()
    def refresh_respondents_from_db(self):
        self.respondent.clear()
        if not self.db:return
        for r in self.db.get_respondents(): self.respondent.addItem(f"{r.get('full_name') or r.get('username')} [{r.get('status')}]",r.get('respondent_id'))
    def rebuild(self):
        while self.form.count():
            x=self.form.takeAt(0); w=x.widget()
            if w:w.deleteLater()
        self.widgets={}
        for q in self.config.get('questions',[]):
            typ=q.get('question_type','').upper(); text=q.get('question_text',''); qid=q.get('question_id')
            if typ in LAYOUT:
                l=QLabel(text); l.setWordWrap(True)
                if typ in {'TITLE','SECTION'}: l.setStyleSheet("font-size:16px;font-weight:bold;margin-top:10px")
                self.form.addWidget(l); continue
            box=QGroupBox(("* " if q.get('required') else "")+text); v=QVBoxLayout(box)
            if q.get('description'): d=QLabel(q['description']); d.setWordWrap(True); d.setStyleSheet("color:#666"); v.addWidget(d)
            w=self.make_widget(q); v.addWidget(w); self.form.addWidget(box); self.widgets[qid]=(w,q,box)
        self.form.addStretch()
    def opts(self,q): return [x.strip() for x in re.split(r'[|;]',q.get('options','')) if x.strip()]
    def make_widget(self,q):
        t=q.get('question_type','').upper(); opts=self.opts(q)
        if t=='LONG_TEXT': w=QPlainTextEdit(); w.setMaximumHeight(100); return w
        if t in {'INTEGER','DECIMAL','SHORT_TEXT','EMAIL','PHONE'}:
            w=QLineEdit(); w.setPlaceholderText('Enter a number' if t in {'INTEGER','DECIMAL'} else 'Enter response'); return w
        if t in {'SINGLE_CHOICE','LIKERT','RATING','DROPDOWN','YES_NO','BOOLEAN'}:
            w=QComboBox(); w.addItem("— Select —",None)
            if t in {'YES_NO','BOOLEAN'} and not opts: opts=['Yes','No']
            if t in {'LIKERT','RATING'} and not opts:
                mn=int(q.get('min_value') or 1); mx=int(q.get('max_value') or 5); opts=[str(x) for x in range(mn,mx+1)]
            for x in opts:w.addItem(x,x)
            return w
        if t=='MULTIPLE_CHOICE':
            w=QListWidget(); w.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection); [w.addItem(x) for x in opts]; w.setMaximumHeight(110); return w
        if t=='DATE': return QDateEdit(QDate.currentDate())
        if t=='TIME': return QTimeEdit(QTime.currentTime())
        if t=='DATETIME': return QDateTimeEdit(QDateTime.currentDateTime())
        return QLineEdit()
    def value(self,w,q):
        t=q.get('question_type','').upper()
        if isinstance(w,QLineEdit): return w.text().strip()
        if isinstance(w,QPlainTextEdit): return w.toPlainText().strip()
        if isinstance(w,QComboBox): return w.currentData()
        if isinstance(w,QListWidget): return [x.text() for x in w.selectedItems()]
        if isinstance(w,QDateEdit): return w.date().toString('yyyy-MM-dd')
        if isinstance(w,QTimeEdit): return w.time().toString('HH:mm:ss')
        if isinstance(w,QDateTimeEdit): return w.dateTime().toString('yyyy-MM-ddTHH:mm:ss')
    def validate(self):
        errors=[]; data={}
        for qid,(w,q,box) in self.widgets.items():
            box.setStyleSheet(''); val=self.value(w,q); t=q.get('question_type','').upper(); empty=val is None or val=='' or val==[]
            err=''
            if q.get('required') and empty: err='This question is required.'
            if not empty and t in {'INTEGER','DECIMAL'}:
                try:
                    num=int(val) if t=='INTEGER' else float(val)
                    mn=q.get('min_value'); mx=q.get('max_value')
                    if mn is not None and num<float(mn): err=f'Value must be at least {mn}.'
                    if mx is not None and num>float(mx): err=f'Value must be at most {mx}.'
                    if not err: val=num
                except ValueError: err='Value must be an integer.' if t=='INTEGER' else 'Value must be a number.'
            if not empty and t=='EMAIL' and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$',str(val)): err='Invalid email address.'
            if err: box.setStyleSheet('QGroupBox{border:2px solid #dc3545;}'); errors.append(f"{q.get('question_text')}: {err}")
            data[qid]=val
        return data,errors
    def save_response(self):
        if not self.db or self.respondent.currentData() is None: QMessageBox.warning(self,'Respondent Required','Please select a respondent.'); return
        data,errors=self.validate()
        if errors: QMessageBox.warning(self,'Validation Error','Please correct the highlighted fields:\n\n'+'\n'.join(errors[:10])); return
        self.db.save_response(self.respondent.currentData(),data); self.refresh_respondents_from_db(); QMessageBox.information(self,'Response Saved','Survey response saved successfully.')
    def open_response_for_edit(self,respondent_id):
        i=self.respondent.findData(respondent_id)
        if i>=0:self.respondent.setCurrentIndex(i)
        row=self.db.get_response_by_respondent(respondent_id) if self.db else None
        if not row:return
        data=json.loads(row['response_json'])
        for qid,val in data.items():
            if qid not in self.widgets:continue
            w,q,_=self.widgets[qid]
            if isinstance(w,QLineEdit):w.setText(str(val if val is not None else ''))
            elif isinstance(w,QPlainTextEdit):w.setPlainText(str(val or ''))
            elif isinstance(w,QComboBox):
                j=w.findData(str(val)); w.setCurrentIndex(j if j>=0 else 0)
            elif isinstance(w,QListWidget):
                vals=set(val or [])
                for k in range(w.count()):w.item(k).setSelected(w.item(k).text() in vals)
    def export(self):
        if not self.db:return
        p,_=QFileDialog.getSaveFileName(self,'Export Survey Data','survey_results.xlsx','Excel (*.xlsx)')
        if not p:return
        if not p.lower().endswith('.xlsx'):p += '.xlsx'
        wb=Workbook(); meta=wb.active; meta.title='Metadata'; m=self.db.get_meta(); [meta.append([k,v]) for k,v in m.items() if k!='config_json']
        qs=self.config.get('questions',[]); ids=[q['question_id'] for q in qs if q.get('question_type') not in LAYOUT]
        dataws=wb.create_sheet('Data'); dataws.append(['Answer_ID','Respondent_ID','Expert_Name','Username','Source_Project','Submitted_At']+ids)
        for r in self.db.get_all_responses():
            d=json.loads(r['response_json']); dataws.append([f"Ans_{int(r['display_index']):02d}",r['respondent_id'],r.get('full_name'),r.get('username'),r.get('source_project_name'),r.get('submitted_at')]+[json.dumps(d.get(i),ensure_ascii=False) if isinstance(d.get(i),list) else d.get(i) for i in ids])
        cw=wb.create_sheet('Codebook'); cw.append(['Question_ID','Question_Text','Question_Type','Required','Options','Min','Max','Description'])
        for q in qs: cw.append([q.get('question_id'),q.get('question_text'),q.get('question_type'),q.get('required'),q.get('options'),q.get('min_value'),q.get('max_value'),q.get('description')])
        rw=wb.create_sheet('Respondent'); rw.append(['Respondent_ID','Username','Full_Name','Organization','Status']); [rw.append([r.get('respondent_id'),r.get('username'),r.get('full_name'),r.get('organization'),r.get('status')]) for r in self.db.get_respondents()]
        wb.save(p); QMessageBox.information(self,'Export Complete',f'Survey data exported successfully.\n\n{p}')
