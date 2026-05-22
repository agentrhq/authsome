"""Global pytest configuration and early initialization."""

import os
import tempfile

# Force a safe temporary AUTHSOME_HOME before any codebase imports occur
_tmp_dir = tempfile.TemporaryDirectory(prefix="authsome_test_home_")
os.environ["AUTHSOME_HOME"] = _tmp_dir.name
os.environ["AUTHSOME_ANALYTICS"] = "0"
