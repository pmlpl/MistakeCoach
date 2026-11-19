"""pytest 友好的前后端 PROVIDERS 一致性测试"""
from test_providers_sync import compare


def test_providers_backend_frontend_in_sync():
    errs = compare()
    assert not errs, "\n".join(errs)
