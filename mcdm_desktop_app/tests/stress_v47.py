import os, sys, tempfile, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.project_db import ProjectDB

MCDM_CFG={
 'model_type':'DEMATEL','use_z_number':False,'scale_type':'Category',
 'continuous_min':0.0,'continuous_max':10.0,'expert_auth_mode':'Account',
 'factors':[{'type':'Factor','code':f'F{i}','name':f'Factor {i}','description':''} for i in range(1,11)],
 'alternatives':[],
 'standard_scales':[{'linguistic':str(i),'code':str(i),'value':i} for i in range(6)],
 'z_scales_a':[],'z_scales_b':[]
}
QBASE={'survey_schema_version':2,'questions':[{'question_id':f'Q{i}','question_text':f'Question {i}','question_type':'LIKERT','required':True} for i in range(1,21)]}
QUALBASE={'qualitative_schema_version':1,'initial_questions':[{'question_id':f'Q{i}','question_text':f'Initial {i}','required':True,'display_order':i} for i in range(1,11)]}

def must(x,msg):
    if not x: raise AssertionError(msg)

def run():
  stats=[]
  with tempfile.TemporaryDirectory() as d:
    # 1) MCDM 200 account lifecycle + update identity + reopen
    p=os.path.join(d,'m.mcdm')
    accounts=[{'Respondent_ID':f'R{i:04d}','Username':f'expert{i}','Password':f'pw{i}','Full_Name':f'Expert {i}','Organization':'Org'} for i in range(200)]
    ProjectDB.create_project(p,'Stress MCDM','MCDM',MCDM_CFG,accounts)
    db=ProjectDB(p)
    t=time.time()
    for i in range(200):
      r=db.authenticate_respondent(f'expert{i}',f'pw{i}'); must(r and r['respondent_id']==f'R{i:04d}',f'login {i}')
      must(db.authenticate_respondent(f'expert{i}','wrong') is None,f'wrong password {i}')
      mat=[[str((r+c+i)%6) for c in range(10)] for r in range(10)]
      db.save_response(r['respondent_id'],{'code_matrix':mat,'value_matrix':mat})
    must(len(db.get_all_responses())==200,'MCDM response count')
    for i in range(0,200,2):
      db.save_response(f'R{i:04d}',{'code_matrix':[['5']*10 for _ in range(10)],'value_matrix':[['5']*10 for _ in range(10)]})
    must(len(db.get_all_responses())==200,'updates must not duplicate')
    db.close(); db=ProjectDB(p); must(len(db.get_all_responses())==200,'reopen persistence'); db.close()
    stats.append(('MCDM 200 accounts/login/save/update/reopen',time.time()-t))

    # 2) Quant free 500 same-name submissions remain distinct
    p=os.path.join(d,'qfree.mcdm'); cfg={**QBASE,'auth_mode':'Free'}
    ProjectDB.create_project(p,'Q Free','QUANTITATIVE_SURVEY',cfg,[]); db=ProjectDB(p); t=time.time()
    ids=[]
    for i in range(500):
      rid=db.create_free_respondent('Same Name'); ids.append(rid); db.save_response(rid,{f'Q{x}':(i+x)%5+1 for x in range(1,21)})
    must(len(set(ids))==500,'free ids unique'); must(len(db.get_all_responses())==500,'free responses 500'); db.close()
    stats.append(('Quant Free 500 submissions',time.time()-t))

    # 3) Quant account login/update
    p=os.path.join(d,'qacc.mcdm'); cfg={**QBASE,'auth_mode':'Account'}
    acc=[{'Username':f'u{i}','Password':'secret','Full_Name':f'U {i}'} for i in range(100)]
    ProjectDB.create_project(p,'Q Acc','QUANTITATIVE_SURVEY',cfg,acc); db=ProjectDB(p); t=time.time()
    for i in range(100):
      r=db.authenticate_respondent(f'u{i}','secret'); must(r,f'quant login {i}'); db.save_response(r['respondent_id'],{'Q1':1}); db.save_response(r['respondent_id'],{'Q1':2})
    must(len(db.get_all_responses())==100,'quant updates no duplicate'); db.close(); stats.append(('Quant Account 100 login/update',time.time()-t))

    # 4) Qual free/account merge despite mode difference
    pa=os.path.join(d,'qualA.mcdm'); pf=os.path.join(d,'qualF.mcdm')
    ProjectDB.create_project(pa,'Qual A','QUALITATIVE_INTERVIEW',{**QUALBASE,'auth_mode':'Account'},[{'Username':'qa','Password':'pw','Full_Name':'QA'}])
    ProjectDB.create_project(pf,'Qual F','QUALITATIVE_INTERVIEW',{**QUALBASE,'auth_mode':'Free'},[])
    a=ProjectDB(pa); f=ProjectDB(pf); rid=f.create_free_respondent('Interviewee'); f.save_response(rid,{'interview_items':[{'sequence':1,'kind':'INITIAL','question_id':'Q1','question':'Initial 1','answer':'A'}]}); f.close()
    must(a.is_merge_compatible(pf),'qual free/account should merge'); a.merge_other_projects([pf]); must(len(a.get_all_responses())==1,'qual merge count'); a.close(); stats.append(('Qual Free↔Account merge',0))

    # 5) Merge blocks real config difference
    p2=os.path.join(d,'qdiff.mcdm'); ProjectDB.create_project(p2,'Diff','QUANTITATIVE_SURVEY',{**QBASE,'auth_mode':'Free','questions':QBASE['questions']+[{'question_id':'QX','question_text':'Different','question_type':'SHORT_TEXT','required':False}]},[])
    a=ProjectDB(os.path.join(d,'qacc.mcdm')); must(not a.is_merge_compatible(p2),'different research config must block'); a.close(); stats.append(('Merge blocks research difference',0))

  print('V4.7 STRESS TEST PASS')
  for name,sec in stats: print(f'PASS | {name} | {sec:.3f}s')

if __name__=='__main__': run()
