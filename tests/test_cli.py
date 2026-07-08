from cli.demo import run


def test_cli_happy_path(capsys):
    code = run(["--member-id", "M-plat-nocruise", "--partner-id", "partner_no_cruise", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 0
    assert "partner_no_cruise" in out
    assert "Platinum" in out
    assert "Cruise" not in out.split("Removed")[0]  # no cruise among shown recs
    assert "category_exclusion" in out


def test_cli_cross_partner_prints_safe_error(capsys):
    code = run(["--member-id", "M-plat-nocruise", "--partner-id", "partner_capped", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 1
    assert "AUTHORIZATION_DENIED" in out


def test_cli_unknown_member_prints_safe_error(capsys):
    code = run(["--member-id", "M-nope", "--partner-id", "partner_capped", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 1
    assert "UNKNOWN_MEMBER" in out
