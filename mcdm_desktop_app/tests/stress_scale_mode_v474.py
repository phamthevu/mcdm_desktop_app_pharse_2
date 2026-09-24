import tempfile
from pathlib import Path
from core.models import ProjectConfig, config_to_dict, config_from_dict
from core.excel_handler import generate_default_template, parse_config_excel

METHODS = ['DEMATEL','TOPSIS','AHP','DELPHI']

def run():
    with tempfile.TemporaryDirectory() as td:
        xlsx = str(Path(td)/'template.xlsx')
        generate_default_template(xlsx)
        n=0
        for method in METHODS:
            for mode in ['Category','Continuous']:
                for z in [False, True]:
                    # Z-number is meaningful for categorical; nevertheless ensure parser never flips mode.
                    cfg=ProjectConfig(model_type=method, scale_type=mode, use_z_number=z,
                                      continuous_min=-2.5, continuous_max=17.75,
                                      expert_auth_mode='Account')
                    out=parse_config_excel(xlsx,cfg)
                    assert out.scale_type == mode, (method,mode,z,out.scale_type)
                    assert out.continuous_min == -2.5
                    assert out.continuous_max == 17.75
                    d=config_to_dict(out)
                    restored=config_from_dict(d)
                    assert restored.scale_type == mode
                    assert restored.continuous_min == -2.5
                    assert restored.continuous_max == 17.75
                    n+=1
        # repeated reload stress
        cfg=ProjectConfig(model_type='TOPSIS', scale_type='Continuous', continuous_min=0.125, continuous_max=99.875, expert_auth_mode='Account')
        for i in range(1000):
            cfg=parse_config_excel(xlsx,cfg)
            assert cfg.scale_type == 'Continuous'
            assert cfg.continuous_min == 0.125 and cfg.continuous_max == 99.875
        print(f'PASS: {n} method/mode/Z scenarios + 1000 repeated Continuous template reloads')
if __name__=='__main__': run()
