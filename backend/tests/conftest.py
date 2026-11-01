import os, sys, tempfile
os.environ.setdefault("CRIS_DATA", tempfile.mkdtemp(prefix="cris-test-"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
