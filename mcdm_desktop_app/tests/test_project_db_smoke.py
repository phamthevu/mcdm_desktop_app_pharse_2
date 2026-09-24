import tempfile, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core.project_db import ProjectDB

CFG={'project_type':'QUANTITATIVE_SURVEY','auth_mode':'Account','questions':[{'question_id':'Q1','question_text':'Q1','question_type':'SHORT_TEXT','required':True}]}

def make(path,name='A',cfg=None,accounts=None):
    ProjectDB.create_project(path,name,'QUANTITATIVE_SURVEY',cfg or CFG,accounts or [])
    return ProjectDB(path)

def test_account_login_and_update_identity():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'a.mcdm'); db=make(p,accounts=[{'username':'u1','password':'secret','full_name':'Alice'}])
        r=db.authenticate_respondent('u1','secret'); assert r and r['full_name']=='Alice'
        assert db.authenticate_respondent('u1','bad') is None
        rid=r['respondent_id']; db.save_response(rid,{'Q1':'first'}); db.save_response(rid,{'Q1':'edited'})
        rows=db.get_all_responses(); assert len(rows)==1 and 'edited' in rows[0]['response_json']; assert rows[0]['respondent_id']==rid
        db.close()

def test_free_submissions_same_name_are_distinct():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'a.mcdm'); db=make(p,cfg={**CFG,'auth_mode':'Free'})
        a=db.create_free_respondent('Same Name'); b=db.create_free_respondent('Same Name'); assert a!=b
        db.save_response(a,{'Q1':'A'}); db.save_response(b,{'Q1':'B'}); assert len(db.get_all_responses())==2
        db.close()

def test_merge_same_config_different_project_identity():
    with tempfile.TemporaryDirectory() as d:
        p1=os.path.join(d,'a.mcdm'); p2=os.path.join(d,'b.mcdm'); a=make(p1,'Project A'); b=make(p2,'Project B')
        r=b.authenticate_respondent('u1','secret') if False else None
        rid=b.add_respondent('b','pw','Bob','Org'); b.save_response(rid,{'Q1':'B'}); b.close()
        assert a.is_merge_compatible(p2); a.merge_other_projects([p2]); assert len(a.get_all_responses())==1; a.close()

def test_merge_account_and_free_same_research_structure():
    with tempfile.TemporaryDirectory() as d:
        p1=os.path.join(d,'account.mcdm'); p2=os.path.join(d,'free.mcdm')
        account_cfg={**CFG,'auth_mode':'Account'}
        free_cfg={**CFG,'auth_mode':'Free'}
        a=make(p1,'Account Project',cfg=account_cfg)
        b=make(p2,'Free Project',cfg=free_cfg)
        # Auth mode must still be persisted for reopening/UI behavior.
        import json
        assert json.loads(a.get_meta()['config_json'])['auth_mode']=='Account'
        assert json.loads(b.get_meta()['config_json'])['auth_mode']=='Free'
        rid=b.create_free_respondent('Free Expert'); b.save_response(rid,{'Q1':'free answer'}); b.close()
        cmp=a.compare_merge_config(p2)
        assert cmp['compatible'], cmp
        a.merge_other_projects([p2])
        assert len(a.get_all_responses())==1
        a.close()

def test_merge_still_blocks_real_research_difference():
    with tempfile.TemporaryDirectory() as d:
        p1=os.path.join(d,'a.mcdm'); p2=os.path.join(d,'b.mcdm')
        a=make(p1,cfg={**CFG,'auth_mode':'Account'})
        changed={**CFG,'auth_mode':'Free','questions':[{'question_id':'Q2','question_text':'Different','question_type':'SHORT_TEXT','required':True}]}
        b=make(p2,cfg=changed); b.close()
        assert not a.is_merge_compatible(p2)
        a.close()
