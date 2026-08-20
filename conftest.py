import sys
from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parent
PLATFORM_DIR = PROJECT_ROOT / "platform"


# Load the standard-library platform module first
stdlib_platform_path = Path(sys.base_prefix) / "Lib" / "platform.py"

spec = importlib.util.spec_from_file_location("platform_stdlib", stdlib_platform_path)
platform_stdlib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform_stdlib)


# Keep standard platform API available
sys.modules["platform"] = platform_stdlib


# Allow project imports like:
# from platform.app import app
# from platform.database import ...
#
# by making stdlib platform behave as a package for pytest.
platform_stdlib.__path__ = [str(PLATFORM_DIR)]
platform_stdlib.__package__ = "platform"