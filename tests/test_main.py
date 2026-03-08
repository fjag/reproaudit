from project2.main import main


def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert "Hello from project2!" in captured.out
