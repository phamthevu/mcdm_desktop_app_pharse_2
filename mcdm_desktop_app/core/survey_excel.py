from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from core.survey_models import SurveyQuestion, SUPPORTED_TYPES

COLS = ["Question_ID","Question_Text","Question_Type","Required","Options","Min_Value","Max_Value","Default_Value","Validation","Description","Display_Order"]

def _bool(v): return str(v).strip().lower() in {"1","true","yes","y","required"}
def _clean(v): return "" if pd.isna(v) else str(v).strip()
def _num(v):
    if pd.isna(v) or str(v).strip()=="": return None
    return float(v)

def parse_survey_excel(path):
    xl = pd.ExcelFile(path)
    qsheet = "Questions" if "Questions" in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=qsheet)
    missing = [c for c in ["Question_ID","Question_Text","Question_Type"] if c not in df.columns]
    if missing: raise ValueError("Missing required columns: " + ", ".join(missing))
    questions=[]; ids=set()
    for i,row in df.iterrows():
        qid=_clean(row.get("Question_ID")); qt=_clean(row.get("Question_Type")).upper()
        if not qid and qt not in {"TITLE","SECTION","DESCRIPTION"}: continue
        if not qid: qid=f"LAYOUT_{i+1}"
        if qid in ids: raise ValueError(f"Duplicate Question_ID: {qid}")
        ids.add(qid)
        if qt not in SUPPORTED_TYPES: raise ValueError(f"Unsupported Question_Type '{qt}' at {qid}")
        mn=_num(row.get("Min_Value")); mx=_num(row.get("Max_Value"))
        if mn is not None and mx is not None and mn > mx: raise ValueError(f"Min_Value > Max_Value at {qid}")
        questions.append(SurveyQuestion(qid,_clean(row.get("Question_Text")),qt,_bool(row.get("Required")),_clean(row.get("Options")),mn,mx,_clean(row.get("Default_Value")),_clean(row.get("Validation")),_clean(row.get("Description")),int(_num(row.get("Display_Order")) or i+1)))
    questions.sort(key=lambda q:q.display_order)
    accounts=[]
    for sheet in ("Accounts","Experts","Respondents"):
        if sheet in xl.sheet_names:
            adf=pd.read_excel(path,sheet_name=sheet)
            for _,r in adf.iterrows():
                u=_clean(r.get("Username"))
                if not u: continue
                accounts.append({"Respondent_ID":_clean(r.get("Respondent_ID")),"Username":u,"Password":_clean(r.get("Password")) or "123","Full_Name":_clean(r.get("Full_Name")) or _clean(r.get("Expert_Name")),"Organization":_clean(r.get("Organization"))})
            break
    return questions, accounts

def generate_survey_template(path):
    wb=Workbook(); ws=wb.active; ws.title="Questions"; ws.append(COLS)
    samples=[
      ["INTRO","Research Survey","TITLE",False,"","","","","","Please answer all applicable questions.",1],
      ["NAME","Full name","SHORT_TEXT",True,"","","","","","",2],
      ["AGE","Age","INTEGER",True,"",18,100,"","","Enter your age in years.",3],
      ["GENDER","Gender","SINGLE_CHOICE",True,"Male|Female|Other","","","","","",4],
      ["SAT1","I am satisfied with this service","LIKERT",True,"1|2|3|4|5",1,5,"","","1 = Strongly disagree; 5 = Strongly agree",5],
      ["INCOME","Monthly income","DECIMAL",False,"",0,1000000000,"","","Numeric value only",6],
      ["COMMENT","Additional comments","LONG_TEXT",False,"","","","","","",7],
    ]
    for x in samples: ws.append(x)
    ac=wb.create_sheet("Accounts"); ac.append(["Respondent_ID","Username","Password","Full_Name","Organization"]); ac.append(["R001","expert01","123","Expert 01","Organization A"])
    for sh in wb.worksheets:
        sh.freeze_panes="A2"; sh.auto_filter.ref=sh.dimensions
        for col in sh.columns:
            sh.column_dimensions[col[0].column_letter].width=min(max(len(str(c.value or "")) for c in col)+2,45)
    Path(path).parent.mkdir(parents=True,exist_ok=True); wb.save(path)
