from types import SimpleNamespace

from app.services.telegram_filters import vacancy_matches_telegram_filters


def test_no_roles_means_no_match():
    vac = SimpleNamespace(title="Backend Python", skills=["Python"], work_format="remote", remote=True)
    assert vacancy_matches_telegram_filters(vac, roles=[], work_formats=None) is False


def test_role_match_in_title():
    vac = SimpleNamespace(title="Senior Backend Engineer", skills=[], work_format="remote", remote=True)
    assert vacancy_matches_telegram_filters(vac, roles=["Backend"], work_formats=None) is True


def test_work_format_filter():
    vac = SimpleNamespace(title="Backend", skills=[], work_format="office", remote=False)
    assert (
        vacancy_matches_telegram_filters(vac, roles=["Backend"], work_formats=["remote"])
        is False
    )
    assert (
        vacancy_matches_telegram_filters(vac, roles=["Backend"], work_formats=["office"])
        is True
    )
