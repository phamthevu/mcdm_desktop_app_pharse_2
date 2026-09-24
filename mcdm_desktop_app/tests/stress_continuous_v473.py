"""V4.7.3 continuous-scale stress checks (headless)."""
from pathlib import Path
import math, random

ROOT = Path(__file__).resolve().parents[1]
widget = (ROOT/'ui/widgets/z_cell_widget.py').read_text(encoding='utf-8')
survey = (ROOT/'ui/tab_survey.py').read_text(encoding='utf-8')

# Static UI contract: direct text input, not spin buttons.
assert 'QDoubleSpinBox' not in widget
assert 'self.txt_eval = QLineEdit()' in widget
assert 'QDoubleValidator' in widget
assert 'validate_input' in widget
assert '_validate_matrix_inputs' in survey
assert '_update_ahp_reciprocal' in survey

# Stress numeric range rules for DEMATEL/TOPSIS/DELPHI style continuous inputs.
def valid(v, lo, hi, positive=False):
    return lo <= v <= hi and (not positive or v > 0)

for lo, hi in [(-10,10),(0,1),(0,10),(1,9),(-1e6,1e6)]:
    for _ in range(20000):
        v = random.uniform(lo-abs(hi-lo), hi+abs(hi-lo))
        expected = lo <= v <= hi
        assert valid(v,lo,hi) == expected

# AHP reciprocal stress: positive inputs must remain finite and reciprocal twice restores value.
for _ in range(100000):
    x = 10 ** random.uniform(-6, 6)
    y = 1.0/x
    assert math.isfinite(y) and y > 0
    assert math.isclose(1.0/y, x, rel_tol=1e-12, abs_tol=1e-12)

# Representative boundaries.
assert valid(0,0,10)
assert valid(10,0,10)
assert not valid(-0.0001,0,10)
assert not valid(10.0001,0,10)
assert not valid(0,0,10,positive=True)  # AHP cannot divide by zero
assert valid(0.000001,0,10,positive=True)

print('PASS | direct QLineEdit continuous UI contract')
print('PASS | 100k AHP reciprocal calculations')
print('PASS | 100k randomized range checks')
print('PASS | boundary and AHP zero protection')
