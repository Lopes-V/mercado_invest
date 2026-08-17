from app.main import main


def test_main_runs(capsys, monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    main()

    captured = capsys.readouterr()

    assert "Investment Bot iniciado [env=test]" in captured.out