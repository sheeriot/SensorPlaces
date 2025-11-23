import os
import unittest

def skip_unless_beta(reason="Skipping Beta Tests"):
    """
    Decorator to skip tests unless RUN_BETA_TESTS environment variable is set.
    """
    return unittest.skipUnless(os.environ.get('RUN_BETA_TESTS') == 'true', reason)
