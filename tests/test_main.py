from app.main import main


def test_main_runs(capsys):
    main()

    captured = capsys.readouterr()

    assert captured.out == "Investment Bot iniciado.\n"