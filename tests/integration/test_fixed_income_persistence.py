import os
import pytest
from app.config.settings import get_settings
from app.database.client import create_supabase_client

pytestmark=pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_FIXED_INCOME_DB_INTEGRATION")!="1",reason="RUN_FIXED_INCOME_DB_INTEGRATION=1 required after remote migration")
def test_fixed_income_persistence_remote_contract():
    assert isinstance(create_supabase_client(get_settings()).table("fixed_income_instruments").select("id").limit(1).execute().data,list)
