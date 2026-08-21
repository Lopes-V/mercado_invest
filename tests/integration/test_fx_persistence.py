import os,pytest
from app.config.settings import get_settings
from app.database.client import create_supabase_client
pytestmark=pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_FX_DB_INTEGRATION")!="1",reason="RUN_FX_DB_INTEGRATION=1 required after remote migration")
def test_fx_persistence_remote_contract(): assert isinstance(create_supabase_client(get_settings()).table("fx_rates").select("id").limit(1).execute().data,list)
