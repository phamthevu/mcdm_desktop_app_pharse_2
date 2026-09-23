from pathlib import Path
import pandas as pd
from openpyxl import Workbook
QUESTION_COLS=["Question_ID","Question_Text","Required","Display_Order"]
def _clean(v): return "" if pd.isna(v) else str(v).strip()
def _bool(v): return str(v).strip().lower() in {"1","true","yes","y","required"}
def parse_qualitative_excel(path):
    xl=pd.ExcelFile(path); sheet="Questions" if "Questions" in xl.sheet_names else xl.sheet_names[0]; df=pd.read_excel(path,sheet_name=sheet)
    missing=[c for c in ("Question_ID","Question_Text") if c not in df.columns]
    if missing: raise ValueError("Missing required columns: "+", ".join(missing))
    questions=[]; seen=set()
    for i,row in df.iterrows():
        qid,text=_clean(row.get("Question_ID")),_clean(row.get("Question_Text"))
        if not qid and not text: continue
        if not qid or not text: raise ValueError(f"Incomplete Questions row {i+2}.")
        if qid in seen: raise ValueError(f"Duplicate Question_ID: {qid}")
        seen.add(qid); raw=row.get("Display_Order"); order=i+1 if pd.isna(raw) or str(raw).strip()=="" else int(float(raw))
        questions.append({"question_id":qid,"question_text":text,"required":_bool(row.get("Required")),"display_order":order})
    if not questions: raise ValueError("At least one initial interview question is required.")
    questions.sort(key=lambda x:x["display_order"]); accounts=[]
    for name in ("Accounts","Respondents","Experts"):
        if name in xl.sheet_names:
            adf=pd.read_excel(path,sheet_name=name)
            for _,r in adf.iterrows():
                u=_clean(r.get("Username"))
                if not u: continue
                accounts.append({"Respondent_ID":_clean(r.get("Respondent_ID")),"Username":u,"Password":_clean(r.get("Password")) or "123","Full_Name":_clean(r.get("Full_Name")) or _clean(r.get("Expert_Name")),"Organization":_clean(r.get("Organization"))})
            break
    return questions,accounts
def qualitative_config_to_dict(questions,auth_mode="Free"):
    return {"qualitative_schema_version":1,"auth_mode":auth_mode,"initial_questions":questions}
def generate_qualitative_template(path):
    wb=Workbook(); ws=wb.active; ws.title="Questions"; ws.append(QUESTION_COLS)
    for row in [["Q01","Can you describe your experience with this topic?",True,1],["Q02","What factors influenced your experience or decision?",True,2],["Q03","What challenges did you encounter?",False,3],["Q04","Is there anything else you would like to add?",False,4]]: ws.append(row)
    ac=wb.create_sheet("Accounts"); ac.append(["Respondent_ID","Username","Password","Full_Name","Organization"]); ac.append(["R001","interview01","123","Participant 01",""])
    for sh in wb.worksheets:
        sh.freeze_panes="A2"
        for col in sh.columns: sh.column_dimensions[col[0].column_letter].width=min(max(len(str(c.value or "")) for c in col)+2,60)
    Path(path).parent.mkdir(parents=True,exist_ok=True); wb.save(path)
