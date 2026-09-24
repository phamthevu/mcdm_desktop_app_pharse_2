import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.project_db import ProjectDB

def must(v,msg):
    if not v: raise AssertionError(msg)

def add_free(db,name,payload):
    rid=db.create_free_respondent(name); db.save_response(rid,payload); return rid

def run():
  with tempfile.TemporaryDirectory() as d:
    # Quant: Free target <- Account source, 120 rows, repeated merge is idempotent.
    qbase={'survey_schema_version':2,'questions':[{'question_id':'Q1','question_text':'Q1','question_type':'LIKERT','required':True}]}
    qt=os.path.join(d,'qt.mcdm'); qs=os.path.join(d,'qs.mcdm')
    ProjectDB.create_project(qt,'QT','QUANTITATIVE_SURVEY',{**qbase,'auth_mode':'Free'},[])
    acc=[{'Username':f'u{i}','Password':'p','Full_Name':f'U{i}'} for i in range(120)]
    ProjectDB.create_project(qs,'QS','QUANTITATIVE_SURVEY',{**qbase,'auth_mode':'Account'},acc)
    s=ProjectDB(qs)
    for i in range(120):
        r=s.authenticate_respondent(f'u{i}','p'); s.save_response(r['respondent_id'],{'Q1':(i%5)+1})
    s.close(); t=ProjectDB(qt)
    must(t.is_merge_compatible(qs),'Quant Free/Account compatibility')
    log=t.merge_other_projects([qs]); must(log[0]['count']==120,'Quant first merge count'); must(len(t.get_all_responses())==120,'Quant target 120')
    before_r=len(t.get_respondents()); log=t.merge_other_projects([qs]); must(log[0]['count']==0,'Quant repeat count zero'); must(len(t.get_all_responses())==120,'Quant no duplicate responses'); must(len(t.get_respondents())==before_r,'Quant no duplicate respondents'); t.close()

    # Qual: Account target <- Free source, follow-ups retained, repeat safe.
    qual={'qualitative_schema_version':1,'initial_questions':[{'question_id':'Q1','question_text':'Why?','required':True,'display_order':1}]}
    at=os.path.join(d,'at.mcdm'); fs=os.path.join(d,'fs.mcdm')
    ProjectDB.create_project(at,'AT','QUALITATIVE_INTERVIEW',{**qual,'auth_mode':'Account'},[{'Username':'owner','Password':'p','Full_Name':'Owner'}])
    ProjectDB.create_project(fs,'FS','QUALITATIVE_INTERVIEW',{**qual,'auth_mode':'Free'},[])
    f=ProjectDB(fs)
    for i in range(80):
        add_free(f,'Same Name',{'interview_items':[{'sequence':'1','kind':'INITIAL','question_id':'Q1','question':'Why?','answer':f'A{i}'},{'sequence':'1.1','kind':'FOLLOW_UP','parent_question_id':'Q1','question_id':None,'question':'More?','answer':f'F{i}'}]})
    f.close(); a=ProjectDB(at); must(a.is_merge_compatible(fs),'Qual Account/Free compatibility'); a.merge_other_projects([fs]); must(len(a.get_all_responses())==80,'Qual 80');
    sample=json.loads(a.get_all_responses()[0]['response_json']); must(len(sample['interview_items'])==2,'Qual follow-up retained'); br=len(a.get_respondents()); a.merge_other_projects([fs]); must(len(a.get_all_responses())==80 and len(a.get_respondents())==br,'Qual repeat idempotent'); a.close()

    # MCDM Account-only: merge 100 responses and reject real config difference.
    mbase={'model_type':'AHP','use_z_number':False,'scale_type':'Category','continuous_min':0.0,'continuous_max':10.0,'expert_auth_mode':'Account','factors':[{'type':'Factor','code':'F1','name':'F1','description':''},{'type':'Factor','code':'F2','name':'F2','description':''}],'alternatives':[],'standard_scales':[{'linguistic':'L','code':'L','value':1}],'z_scales_a':[],'z_scales_b':[]}
    mt=os.path.join(d,'mt.mcdm'); ms=os.path.join(d,'ms.mcdm'); md=os.path.join(d,'md.mcdm')
    ProjectDB.create_project(mt,'MT','MCDM',mbase,[{'Username':'t','Password':'p','Full_Name':'T'}])
    acc=[{'Username':f'e{i}','Password':'p','Full_Name':f'E{i}'} for i in range(100)]; ProjectDB.create_project(ms,'MS','MCDM',mbase,acc)
    s=ProjectDB(ms)
    for i in range(100):
        r=s.authenticate_respondent(f'e{i}','p'); s.save_response(r['respondent_id'],{'code_matrix':[['1','L'],['1','1']],'value_matrix':[[1,1],[1,1]]})
    s.close(); t=ProjectDB(mt); t.merge_other_projects([ms]); must(len(t.get_all_responses())==100,'MCDM 100'); t.merge_other_projects([ms]); must(len(t.get_all_responses())==100,'MCDM repeat safe'); t.close()
    diff={**mbase,'factors':mbase['factors']+[{'type':'Factor','code':'F3','name':'F3','description':''}]}; ProjectDB.create_project(md,'MD','MCDM',diff,[]); t=ProjectDB(mt); must(not t.is_merge_compatible(md),'MCDM diff blocked'); t.close()

    # Batch folder-style merge: 5 compatible quant sources x 30 = 150.
    target=os.path.join(d,'batch_target.mcdm'); ProjectDB.create_project(target,'BT','QUANTITATIVE_SURVEY',{**qbase,'auth_mode':'Free'},[])
    paths=[]
    for j in range(5):
        p=os.path.join(d,f'b{j}.mcdm'); ProjectDB.create_project(p,f'B{j}','QUANTITATIVE_SURVEY',{**qbase,'auth_mode':'Free'},[]); x=ProjectDB(p)
        for i in range(30): add_free(x,f'P{j}-{i}',{'Q1':1})
        x.close(); paths.append(p)
    x=ProjectDB(target); logs=x.merge_other_projects(paths); must(sum(z['count'] for z in logs)==150,'Batch imported 150'); must(len(x.get_all_responses())==150,'Batch response total'); x.merge_other_projects(paths); must(len(x.get_all_responses())==150,'Batch repeat safe'); must(len(x.get_merge_history())==10,'Merge history records attempts'); x.close()

  print('V4.7.2 MERGE STRESS PASS')
  print('PASS | Quant Free<-Account 120 + repeat idempotency')
  print('PASS | Qual Account<-Free 80 + follow-ups + repeat idempotency')
  print('PASS | MCDM Account 100 + repeat + incompatible block')
  print('PASS | Batch 5 sources x 30 = 150 + repeat')

if __name__=='__main__': run()
