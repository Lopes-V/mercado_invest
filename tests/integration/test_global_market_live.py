import os,pytest
pytestmark=pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_GLOBAL_MARKET_INTEGRATION")!="1",reason="RUN_GLOBAL_MARKET_INTEGRATION=1 required")
def test_global_market_requires_configuration():
    assert os.getenv("TWELVE_DATA_API_KEY") and os.getenv("GLOBAL_TEST_SYMBOL"), "TWELVE_DATA_API_KEY and GLOBAL_TEST_SYMBOL are required"
