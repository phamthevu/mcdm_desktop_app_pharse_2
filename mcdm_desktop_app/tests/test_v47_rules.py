from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_mcdm_free_entry_not_exposed():
    s=(ROOT/'ui'/'tab_config.py').read_text(encoding='utf-8')
    assert 'self.rb_expert_free.setVisible(False)' in s
    assert 'self.config.expert_auth_mode = "Account"' in s

def test_merge_ignores_auth_mode():
    s=(ROOT/'core'/'project_db.py').read_text(encoding='utf-8')
    assert '"auth_mode", "expert_auth_mode", "respondent_mode", "access_mode"' in s
