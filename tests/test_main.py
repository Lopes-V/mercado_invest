from app.main import main


def test_main_runs(capsys, monkeypatch):
    monkeypatch.setenv(
        "APP_ENV",
        "test",
    )
    monkeypatch.setenv(
        "LOG_LEVEL",
        "INFO",
    )
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SECRET_KEY",
        "fake-secret",
    )

    main()

    captured = capsys.readouterr()

    assert (
        "Investment Bot iniciado [env=test]"
        in captured.out
    )