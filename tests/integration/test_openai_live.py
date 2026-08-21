import os,pytest
pytestmark=pytest.mark.integration
@pytest.mark.skipif(os.getenv("RUN_OPENAI_INTEGRATION")!="1",reason="RUN_OPENAI_INTEGRATION=1 required")
def test_openai_live_requires_key():
    assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY is required when RUN_OPENAI_INTEGRATION=1"
