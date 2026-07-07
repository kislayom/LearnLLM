import sys
sys.path.insert(0, ".")
import config, billing, report, inspect
assert config.TAX_RATE == 0.19
assert billing.total_with_tax(100) == 119.0
assert report.tax_portion(100) == 19.0
for mod in (billing, report):
    src = inspect.getsource(mod)
    assert "0.19" not in src, f"{mod.__name__} still hard-codes 0.19"
    assert "config" in src or "TAX_RATE" in src
print("ok")
