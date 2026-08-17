from app.main import main


def test_main_runs(capsys, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    main()

    captured = capsys.readouterr()

    assert (
        captured.out
        == "Investment Bot iniciado [env=development]\n"
    )