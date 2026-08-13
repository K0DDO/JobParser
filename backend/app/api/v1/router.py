from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings as env_settings
from app.db.session import get_db
from app.models import (
    Application,
    ApplicationEvent,
    Notification,
    SearchProfile,
    SourceConfig,
    SystemLog,
    Vacancy,
)
from app.schemas import (
    ApplicationEventOut,
    ApplicationOut,
    ApplicationUpdate,
    ApplyRequest,
    DashboardStats,
    MessageOut,
    NotificationOut,
    SearchProfileCreate,
    SearchProfileOut,
    SearchProfileUpdate,
    SettingsOut,
    SettingsUpdate,
    SourceOut,
    SourceUpdate,
    SyncStatusOut,
    SystemLogOut,
    VacancyFilterOptions,
    VacancyListResponse,
    VacancyOut,
)
from app.scheduler.jobs import reschedule_from_db, trigger_manual_sync
from app.services.applications import manual_apply, transition_status
from app.services.automation import emergency_stop
from app.services.currency import fx_status, refresh_rates
from app.services.hh_auth import (
    build_authorize_url,
    exchange_code,
    get_hh_source,
    probe_hh,
    resolve_access_token,
    save_tokens,
)
from app.services.logging_service import add_log
from app.services.settings_service import get_or_create_settings
from app.services.sync import clear_stale_sync_lock
from app.services.vacancies import get_dashboard_stats, get_filter_options, list_vacancies, vacancy_to_out


def _source_out(source: SourceConfig) -> SourceOut:
    token = resolve_access_token(source) if source.name == "hh" else ""
    return SourceOut(
        id=source.id,
        name=source.name,
        display_name=source.display_name,
        parsing_enabled=source.parsing_enabled,
        auto_apply_enabled=source.auto_apply_enabled,
        auto_apply_supported=source.auto_apply_supported,
        status=source.status,
        last_sync_at=source.last_sync_at,
        last_error=source.last_error,
        found_today=source.found_today,
        connected=bool(token) if source.name == "hh" else source.status == "ready",
    )

router = APIRouter()


def _app_out(app: Application) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        vacancy_id=app.vacancy_id,
        profile_id=app.profile_id,
        status=app.status,
        applied_at=app.applied_at,
        response_at=app.response_at,
        notes=app.notes,
        is_auto=app.is_auto,
        is_dry_run=app.is_dry_run,
        error_message=app.error_message,
        created_at=app.created_at,
        updated_at=app.updated_at,
        vacancy_title=app.vacancy.title if app.vacancy else None,
        vacancy_company=app.vacancy.company if app.vacancy else None,
        vacancy_source=app.vacancy.source if app.vacancy else None,
        vacancy_url=app.vacancy.url if app.vacancy else None,
        profile_name=app.profile.name if app.profile else None,
    )


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/fx/rates")
async def get_fx_rates() -> dict:
    """Current RUB conversion rates (CBR, cached)."""
    return fx_status()


@router.post("/fx/refresh")
async def refresh_fx_rates() -> dict:
    """Force-refresh FX rates from CBR."""
    return await refresh_rates(force=True)


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    return await get_dashboard_stats(db)


@router.get("/vacancies", response_model=VacancyListResponse)
async def get_vacancies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: str | None = Query(None, description="Comma-separated sources"),
    status: str | None = Query(None, description="Comma-separated statuses"),
    q: str | None = None,
    city: str | None = Query(None, description="Comma-separated cities"),
    work_format: str | None = Query(None, description="Comma-separated formats"),
    remote: bool | None = None,
    experience: str | None = Query(None, description="Comma-separated experience levels"),
    salary_from: int | None = None,
    salary_to: int | None = None,
    currency: str | None = None,
    skill: str | None = Query(None, description="Comma-separated skills"),
    role: str | None = Query(None, description="Comma-separated roles"),
    company: str | None = Query(None, description="Comma-separated companies"),
    max_age_hours: int | None = Query(None, ge=1),
    has_salary: bool | None = None,
    employment_type: str | None = Query(None, description="Comma-separated employment types"),
    application_status: str | None = Query(None, description="Comma-separated application statuses"),
    profile_id: str | None = Query(None, description="Comma-separated profile ids"),
    sort: str = Query("published_at"),
    db: AsyncSession = Depends(get_db),
) -> VacancyListResponse:
    items, total = await list_vacancies(
        db,
        page=page,
        page_size=page_size,
        source=source,
        status=status,
        q=q,
        city=city,
        work_format=work_format,
        remote=remote,
        experience=experience,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        skill=skill,
        role=role,
        company=company,
        max_age_hours=max_age_hours,
        has_salary=has_salary,
        employment_type=employment_type,
        application_status=application_status,
        profile_id=profile_id,
        sort=sort,
    )
    return VacancyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/vacancies/options", response_model=VacancyFilterOptions)
async def vacancy_options(db: AsyncSession = Depends(get_db)) -> VacancyFilterOptions:
    data = await get_filter_options(db)
    return VacancyFilterOptions(**data)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(vacancy_id: int, db: AsyncSession = Depends(get_db)) -> VacancyOut:
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Vacancy not found")
    app_result = await db.execute(
        select(Application)
        .options(selectinload(Application.profile))
        .where(Application.vacancy_id == vacancy_id)
        .order_by(Application.id.desc())
        .limit(1)
    )
    app = app_result.scalar_one_or_none()
    return vacancy_to_out(
        vacancy,
        matched_profiles=[app.profile.name] if app and app.profile else [],
        application_status=app.status if app else None,
    )


@router.post("/vacancies/{vacancy_id}/apply", response_model=ApplicationOut)
async def apply_vacancy(
    vacancy_id: int,
    body: ApplyRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Vacancy not found")
    body = body or ApplyRequest()
    settings = await get_or_create_settings(db)
    app = await manual_apply(
        db,
        vacancy,
        profile_id=body.profile_id,
        cover_letter=body.cover_letter,
        force_dry_run=settings.dry_run and settings.global_auto_apply is False and False,
    )
    # Manual apply always attempts real apply unless dry_run globally forces tracking-only —
    # Spec: Dry Run affects auto-apply. Manual apply is real when supported.
    await db.commit()
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == app.id)
    )
    return _app_out(result.scalar_one())


@router.post("/vacancies/{vacancy_id}/ignore", response_model=ApplicationOut)
async def ignore_vacancy(vacancy_id: int, db: AsyncSession = Depends(get_db)) -> ApplicationOut:
    vacancy = await db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(404, "Vacancy not found")
    vacancy.status = "ignored"
    app = Application(vacancy_id=vacancy.id, status="ignored")
    db.add(app)
    await db.flush()
    await db.commit()
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == app.id)
    )
    return _app_out(result.scalar_one())


@router.get("/applications", response_model=list[ApplicationOut])
async def get_applications(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationOut]:
    stmt = select(Application).options(
        selectinload(Application.vacancy), selectinload(Application.profile)
    )
    if status:
        stmt = stmt.where(Application.status == status)
    stmt = stmt.order_by(Application.updated_at.desc())
    result = await db.execute(stmt)
    return [_app_out(a) for a in result.scalars().all()]


@router.get("/applications/{application_id}", response_model=ApplicationOut)
async def get_application(application_id: int, db: AsyncSession = Depends(get_db)) -> ApplicationOut:
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")
    return _app_out(app)


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
async def patch_application(
    application_id: int,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")
    if body.notes is not None:
        app.notes = body.notes
    if body.status is not None:
        await transition_status(db, app, body.status, f"Status updated to {body.status}")
    await db.commit()
    await db.refresh(app)
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == application_id)
    )
    return _app_out(result.scalar_one())


@router.get("/applications/{application_id}/events", response_model=list[ApplicationEventOut])
async def get_application_events(
    application_id: int, db: AsyncSession = Depends(get_db)
) -> list[ApplicationEventOut]:
    result = await db.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.created_at.asc())
    )
    return [ApplicationEventOut.model_validate(e) for e in result.scalars().all()]


@router.get("/profiles", response_model=list[SearchProfileOut])
async def get_profiles(db: AsyncSession = Depends(get_db)) -> list[SearchProfileOut]:
    result = await db.execute(select(SearchProfile).order_by(SearchProfile.id))
    return [SearchProfileOut.model_validate(p) for p in result.scalars().all()]


@router.post("/profiles", response_model=SearchProfileOut)
async def create_profile(
    body: SearchProfileCreate, db: AsyncSession = Depends(get_db)
) -> SearchProfileOut:
    profile = SearchProfile(**body.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return SearchProfileOut.model_validate(profile)


@router.patch("/profiles/{profile_id}", response_model=SearchProfileOut)
async def update_profile(
    profile_id: int, body: SearchProfileUpdate, db: AsyncSession = Depends(get_db)
) -> SearchProfileOut:
    profile = await db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return SearchProfileOut.model_validate(profile)


@router.delete("/profiles/{profile_id}", response_model=MessageOut)
async def delete_profile(profile_id: int, db: AsyncSession = Depends(get_db)) -> MessageOut:
    profile = await db.get(SearchProfile, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    await db.delete(profile)
    await db.commit()
    return MessageOut(message="deleted")


@router.get("/sources", response_model=list[SourceOut])
async def get_sources(db: AsyncSession = Depends(get_db)) -> list[SourceOut]:
    result = await db.execute(select(SourceConfig).order_by(SourceConfig.id))
    return [_source_out(s) for s in result.scalars().all()]


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: int, body: SourceUpdate, db: AsyncSession = Depends(get_db)
) -> SourceOut:
    source = await db.get(SourceConfig, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("auto_apply_enabled") and not source.auto_apply_supported:
        raise HTTPException(400, f"Auto-apply is not supported for {source.display_name}")
    for key, value in data.items():
        setattr(source, key, value)
    await db.commit()
    await db.refresh(source)
    return _source_out(source)


@router.get("/settings", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await get_or_create_settings(db)
    return SettingsOut.model_validate(settings)


@router.patch("/settings", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate, db: AsyncSession = Depends(get_db)
) -> SettingsOut:
    settings = await get_or_create_settings(db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, key, value)
    await db.commit()
    await db.refresh(settings)
    if body.sync_interval_minutes is not None:
        await reschedule_from_db()
        await db.refresh(settings)
    return SettingsOut.model_validate(settings)


@router.post("/sync", response_model=MessageOut)
async def sync_now(background: BackgroundTasks, db: AsyncSession = Depends(get_db)) -> MessageOut:
    unlocked = await clear_stale_sync_lock(db)
    settings = await get_or_create_settings(db)
    if settings.sync_in_progress:
        return MessageOut(message="Sync already in progress", detail="busy")
    background.add_task(trigger_manual_sync)
    msg = "Sync started"
    if unlocked:
        msg = "Sync started (cleared stale lock)"
    return MessageOut(message=msg)


@router.post("/sync/unlock", response_model=MessageOut)
async def sync_unlock(db: AsyncSession = Depends(get_db)) -> MessageOut:
    settings = await get_or_create_settings(db)
    if not settings.sync_in_progress:
        return MessageOut(message="Sync was not locked")
    settings.sync_in_progress = False
    settings.system_status = "ok"
    await add_log(db, "Sync lock released manually", level="warning", category="sync")
    await db.commit()
    return MessageOut(message="Sync lock released")


@router.get("/sync/status", response_model=SyncStatusOut)
async def sync_status(db: AsyncSession = Depends(get_db)) -> SyncStatusOut:
    await clear_stale_sync_lock(db)
    settings = await get_or_create_settings(db)
    return SyncStatusOut(
        sync_in_progress=settings.sync_in_progress,
        last_sync_at=settings.last_sync_at,
        next_sync_at=settings.next_sync_at,
        system_status=settings.system_status,
    )


@router.get("/logs", response_model=list[SystemLogOut])
async def get_logs(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[SystemLogOut]:
    result = await db.execute(
        select(SystemLog).order_by(SystemLog.created_at.desc()).limit(limit)
    )
    return [SystemLogOut.model_validate(x) for x in result.scalars().all()]


@router.get("/notifications", response_model=list[NotificationOut])
async def get_notifications(db: AsyncSession = Depends(get_db)) -> list[NotificationOut]:
    result = await db.execute(
        select(Notification).order_by(Notification.created_at.desc()).limit(50)
    )
    return [NotificationOut.model_validate(n) for n in result.scalars().all()]


@router.post("/automation/enable", response_model=SettingsOut)
async def enable_automation(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await get_or_create_settings(db)
    settings.global_auto_apply = True
    await add_log(db, "Global Auto Apply ENABLED", level="warning", category="auto_apply")
    await db.commit()
    await db.refresh(settings)
    return SettingsOut.model_validate(settings)


@router.post("/automation/disable", response_model=SettingsOut)
async def disable_automation(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await get_or_create_settings(db)
    settings.global_auto_apply = False
    await add_log(db, "Global Auto Apply DISABLED", category="auto_apply")
    await db.commit()
    await db.refresh(settings)
    return SettingsOut.model_validate(settings)


@router.post("/automation/emergency-stop", response_model=SettingsOut)
async def stop_automation(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings = await emergency_stop(db)
    return SettingsOut.model_validate(settings)


@router.get("/auth/hh/status")
async def hh_auth_status(db: AsyncSession = Depends(get_db)) -> dict:
    source = await get_hh_source(db)
    token = resolve_access_token(source)
    probe = await probe_hh(token or None)
    return {
        "client_id_set": bool(env_settings.hh_client_id),
        "client_secret_set": bool(env_settings.hh_client_secret),
        "user_agent": env_settings.hh_user_agent,
        "redirect_uri": env_settings.hh_redirect_uri,
        "connected": bool(token),
        "probe": probe,
    }


@router.get("/auth/hh/login")
async def hh_login() -> RedirectResponse:
    try:
        url = build_authorize_url()
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(url)


@router.get("/auth/hh/callback", response_class=HTMLResponse)
async def hh_callback(
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    if error:
        return HTMLResponse(
            f"<h2>HH отказал в доступе</h2><p>{error}: {error_description or ''}</p>",
            status_code=400,
        )
    if not code:
        return HTMLResponse("<h2>Нет code в callback</h2>", status_code=400)
    try:
        payload = await exchange_code(code)
        await save_tokens(db, payload)
        await add_log(db, "HH OAuth connected", level="success", category="hh")
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(f"<h2>Не удалось получить токен HH</h2><p>{exc}</p>", status_code=400)
    return HTMLResponse(
        """
        <html><body style="font-family: sans-serif; background:#0e1116; color:#e8eef7; padding:40px">
        <h2>HH подключён</h2>
        <p>Токен сохранён локально. Можно закрыть это окно, открыть JobParser и нажать «Синхронизировать сейчас».</p>
        </body></html>
        """
    )
