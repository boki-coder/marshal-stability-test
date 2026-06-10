import marshal
import hashlib


def get_marshal_hash(obj):
    """
    Serialize a Python object and return its SHA256 hash.
    """
    serialized_bytes = marshal.dumps(obj)
    return hashlib.sha256(serialized_bytes).hexdigest()
