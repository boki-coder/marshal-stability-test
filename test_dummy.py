from utils import get_marshal_hash

def test_pipeline_works():
    assert 1 == 1

def test_hash_utility():
    hash_val = get_marshal_hash(12345)
    assert isinstance(hash_val, str)
    assert len(hash_val) == 64