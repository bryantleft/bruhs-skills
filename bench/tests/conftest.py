"""Every test gets private TMPDIRs (``sandbox.tmp_dir``) under its own short base in
/private/tmp, never the real ``/private/tmp/bb`` that live runs use."""

import os
import shutil
import tempfile

import pytest


@pytest.fixture(autouse=True, scope="session")
def _short_tmp_base():
    base = tempfile.mkdtemp(prefix="bbt-", dir="/private/tmp")
    old = os.environ.get("BRUHSBENCH_TMP")
    os.environ["BRUHSBENCH_TMP"] = base
    try:
        yield base
    finally:
        if old is None:
            os.environ.pop("BRUHSBENCH_TMP", None)
        else:
            os.environ["BRUHSBENCH_TMP"] = old
        shutil.rmtree(base, ignore_errors=True)
