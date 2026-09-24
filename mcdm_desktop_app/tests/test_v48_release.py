from pathlib import Path
from core.models import ProjectConfig, config_to_dict, config_from_dict

# New MCDM config is canonical linguistic/category only.
for method in ['DEMATEL','TOPSIS','AHP','DELPHI']:
    for z in [False, True]:
        cfg=ProjectConfig(model_type=method,use_z_number=z,scale_type='Category',continuous_min=-99,continuous_max=999,expert_auth_mode='Account')
        d=config_to_dict(cfg)
        assert d['scale_type']=='Category'
        assert 'continuous_min' not in d and 'continuous_max' not in d
        out=config_from_dict(d)
        assert out.scale_type=='Category' and out.model_type==method and out.use_z_number==z

# Legacy Continuous is rejected explicitly, never silently converted.
try:
    config_from_dict({'model_type':'AHP','scale_type':'Continuous'})
    raise AssertionError('legacy continuous should be rejected')
except ValueError as e:
    assert 'not supported in V4.8' in str(e)

# UI contract: no Continuous selector / Min / Max controls remain in MCDM config.
src=Path('ui/tab_config.py').read_text(encoding='utf-8')
for forbidden in ['rb_continuous','spin_min','spin_max','Continuous (Numerical']:
    assert forbidden not in src, forbidden
assert 'Linguistic / Categorical Scale' in src
print('V4.8 RELEASE RULES PASS | 8 method/Z scenarios | legacy guard | UI continuous removal')
