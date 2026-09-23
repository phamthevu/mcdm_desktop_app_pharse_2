import json
from openpyxl import Workbook
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QMessageBox,QPlainTextEdit,QGroupBox,QScrollArea,QFileDialog
class TabQualInterview(QWidget):
    def __init__(self):
        super().__init__(); self.config={}; self.db=None; self.logged_in_respondent_id=None; self.initial_widgets=[]; self.followups=[]; self.editing_respondent_id=None; root=QVBoxLayout(self)
        self.access=QGroupBox("Participant"); ar=QHBoxLayout(self.access); self.user=QLineEdit(); self.user.setPlaceholderText("Username"); self.password=QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password); self.password.setPlaceholderText("Password"); login=QPushButton("Login"); login.clicked.connect(self.login); self.login_state=QLabel("Not logged in"); ar.addWidget(self.user); ar.addWidget(self.password); ar.addWidget(login); ar.addWidget(self.login_state); ar.addStretch(); root.addWidget(self.access)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); self.host=QWidget(); self.form=QVBoxLayout(self.host); scroll.setWidget(self.host); root.addWidget(scroll,1)
        bar=QHBoxLayout(); add=QPushButton("+ Add Follow-up Question & Answer"); add.clicked.connect(lambda _checked=False: self.add_followup()); rem=QPushButton("Remove Last Follow-up"); rem.clicked.connect(self.remove_last_followup); save=QPushButton("SAVE INTERVIEW"); save.clicked.connect(self.save_response); exp=QPushButton("Export Interviews..."); exp.clicked.connect(self.export); bar.addWidget(add); bar.addWidget(rem); bar.addStretch(); bar.addWidget(exp); bar.addWidget(save); root.addLayout(bar)
    def load_project(self,config,db):self.config=config; self.db=db; self.logged_in_respondent_id=None; self.editing_respondent_id=None; self.build_form()
    def refresh_respondents_from_db(self):pass
    def build_form(self):
        while self.form.count():
            it=self.form.takeAt(0); w=it.widget()
            if w:w.deleteLater()
        self.initial_widgets=[]; self.followups=[]; t=QLabel("IN-DEPTH INTERVIEW TRANSCRIPT"); t.setStyleSheet("font-size:18px;font-weight:bold"); self.form.addWidget(t); note=QLabel("Record answers to the initial guide, then append probing/follow-up question and answer pairs in the exact order they occur."); note.setWordWrap(True); self.form.addWidget(note)
        for i,q in enumerate(self.config.get('initial_questions',[]),1):
            box=QGroupBox(f"{i}. {q.get('question_text','')}"); v=QVBoxLayout(box); a=QPlainTextEdit(); a.setPlaceholderText("Record the participant's answer..."); a.setMinimumHeight(100); v.addWidget(a); self.form.addWidget(box); self.initial_widgets.append((q,a,box))
        self.followup_container=QWidget(); self.followup_layout=QVBoxLayout(self.followup_container); self.followup_layout.setContentsMargins(0,0,0,0); self.form.addWidget(self.followup_container); self.form.addStretch(); self.access.setVisible(self.config.get('auth_mode','Free')=='Account')
    def login(self):
        r=self.db.authenticate_respondent(self.user.text(),self.password.text()) if self.db else None
        if not r:QMessageBox.warning(self,"Login Failed","Invalid username or password."); return
        self.logged_in_respondent_id=r['respondent_id']; self.login_state.setText(f"Logged in: {r.get('full_name') or r.get('username')}"); QMessageBox.information(self,"Login Successful","Participant account authenticated successfully.")
    def add_followup(self, question="", answer=""):
        # QPushButton.clicked emits a bool. Keep this method string-only because it is also
        # called programmatically when restoring saved follow-up questions.
        if isinstance(question, bool):
            question = ""
        if isinstance(answer, bool):
            answer = ""
        n=len(self.initial_widgets)+len(self.followups)+1; box=QGroupBox(f"{n}. Follow-up / Probing Question"); v=QVBoxLayout(box); q=QLineEdit(); q.setPlaceholderText("Enter follow-up question asked by interviewer"); q.setText(question); a=QPlainTextEdit(); a.setPlaceholderText("Record participant's answer"); a.setPlainText(answer); a.setMinimumHeight(90); v.addWidget(QLabel("Question")); v.addWidget(q); v.addWidget(QLabel("Answer")); v.addWidget(a); self.followup_layout.addWidget(box); self.followups.append((q,a,box))
    def remove_last_followup(self):
        if self.followups:
            _,_,b=self.followups.pop(); b.setParent(None); b.deleteLater()
    def _collect(self):
        items=[]; errors=[]; seq=1
        for q,w,box in self.initial_widgets:
            box.setStyleSheet(''); ans=w.toPlainText().strip()
            if q.get('required') and not ans:box.setStyleSheet('QGroupBox{border:2px solid #dc3545;}'); errors.append(q.get('question_text'))
            items.append({"sequence":seq,"kind":"INITIAL","question_id":q.get('question_id'),"question":q.get('question_text'),"answer":ans}); seq+=1
        for q,a,box in self.followups:
            box.setStyleSheet(''); qt=q.text().strip(); at=a.toPlainText().strip()
            if not qt and not at:continue
            if not qt or not at:box.setStyleSheet('QGroupBox{border:2px solid #dc3545;}'); errors.append(f"Follow-up #{seq}: both question and answer are required"); continue
            items.append({"sequence":seq,"kind":"FOLLOW_UP","question_id":None,"question":qt,"answer":at}); seq+=1
        return {"interview_items":items},errors
    def save_response(self):
        if not self.db:return
        mode=self.config.get('auth_mode','Free')
        if mode=='Account' and not self.logged_in_respondent_id:QMessageBox.warning(self,"Login Required","Please log in before saving the interview."); return
        data,errors=self._collect()
        if errors:QMessageBox.warning(self,"Validation Error","Please complete the highlighted interview items:\n\n"+'\n'.join(errors[:10])); return
        rid=self.editing_respondent_id or (self.db.create_anonymous_respondent() if mode=='Free' else self.logged_in_respondent_id); self.db.save_response(rid,data); self.editing_respondent_id=rid; QMessageBox.information(self,"Interview Saved",f"Interview saved successfully.\n\nItems recorded: {len(data['interview_items'])}")
    def open_response_for_edit(self,respondent_id):
        row=self.db.get_response_by_respondent(respondent_id) if self.db else None
        if not row:return
        self.editing_respondent_id=respondent_id; items=json.loads(row['response_json']).get('interview_items',[]); initial={x.get('question_id'):x for x in items if x.get('kind')=='INITIAL'}
        for q,w,_ in self.initial_widgets:w.setPlainText(str(initial.get(q.get('question_id'),{}).get('answer','')))
        while self.followups:self.remove_last_followup()
        for x in items:
            if x.get('kind')=='FOLLOW_UP':self.add_followup(str(x.get('question','')),str(x.get('answer','')))
    def export(self):
        if not self.db:return
        p,_=QFileDialog.getSaveFileName(self,"Export Qualitative Interviews","qualitative_interviews.xlsx","Excel (*.xlsx)")
        if not p:return
        if not p.lower().endswith('.xlsx'):p+='.xlsx'
        wb=Workbook(); meta=wb.active; meta.title='Metadata'; m=self.db.get_meta(); [meta.append([k,v]) for k,v in m.items() if k!='config_json']; lookup=wb.create_sheet('Lookup'); lookup.append(['Interview_ID','Respondent_ID','Participant_Name','Username','Source_Project','Submitted_At','Total_Items'])
        for r in self.db.get_all_responses():
            iid=f"Interview_{int(r['display_index']):02d}"; items=json.loads(r['response_json']).get('interview_items',[]); lookup.append([iid,r.get('respondent_id'),r.get('full_name'),r.get('username'),r.get('source_project_name'),r.get('submitted_at'),len(items)]); ws=wb.create_sheet(iid[:31]); ws.append(['Sequence','Type','Question_ID','Question','Answer'])
            for x in items:ws.append([x.get('sequence'),x.get('kind'),x.get('question_id'),x.get('question'),x.get('answer')])
            ws.column_dimensions['D'].width=60; ws.column_dimensions['E'].width=80
        guide=wb.create_sheet('Initial_Guide'); guide.append(['Question_ID','Question_Text','Required','Display_Order'])
        for q in self.config.get('initial_questions',[]):guide.append([q.get('question_id'),q.get('question_text'),q.get('required'),q.get('display_order')])
        wb.save(p); QMessageBox.information(self,"Export Complete",f"Qualitative interviews exported successfully.\n\n{p}")
