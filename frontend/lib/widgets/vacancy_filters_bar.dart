import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../core/vacancy_filters.dart';
import '../theme/app_theme.dart';
import 'filter_icons.dart';

enum _FilterSection {
  stack,
  role,
  portal,
  format,
  experience,
  salary,
  status,
  application,
  sort,
  age,
  employment,
  city,
  company,
  profile,
  manual,
}

class VacancyFiltersBar extends StatefulWidget {
  const VacancyFiltersBar({super.key});

  @override
  State<VacancyFiltersBar> createState() => _VacancyFiltersBarState();
}

class _VacancyFiltersBarState extends State<VacancyFiltersBar> {
  late final TextEditingController qCtrl;
  late final TextEditingController cityCtrl;
  late final TextEditingController companyCtrl;
  late final TextEditingController skillCtrl;
  late final TextEditingController salaryFromCtrl;
  late final TextEditingController salaryToCtrl;
  bool collapsed = false;
  _FilterSection section = _FilterSection.role;

  static const languages = [
    'Python',
    'Go',
    'Java',
    'JavaScript',
    'TypeScript',
    'Kotlin',
    'PHP',
    'C#',
    'C++',
    'Rust',
    'Ruby',
    'Swift',
    'Scala',
    'SQL',
    'React',
    'Vue',
    'Django',
    'FastAPI',
    'Flask',
    'Spring',
    'Docker',
    'Kubernetes',
    'AWS',
    'PostgreSQL',
    'Redis',
    'Kafka',
    'Node.js',
    'Flutter',
  ];

  static const roles = [
    'Backend',
    'Frontend',
    'Fullstack',
    'Mobile',
    'Android',
    'iOS',
    'QA',
    'DevOps',
    'SRE',
    'Data',
    'ML',
    'Analyst',
    'Architect',
    'Manager',
    'Embedded',
    'Security',
    'Python',
    'Java',
    'Go',
  ];

  /// S → A → B; value — строка для поиска в API
  static const featuredCompanies = <({String label, String query})>[
    (label: 'Avito', query: 'Avito'),
    (label: 'X5 Tech', query: 'X5'),
    (label: 'VK', query: 'VK'),
    (label: 'Raiffeisen', query: 'Райффайзен'),
    (label: 'Ozon', query: 'Ozon'),
    (label: 'Яндекс', query: 'Яндекс'),
    (label: 'Сбер', query: 'Сбер'),
    (label: 'hh.ru', query: 'HeadHunter'),
    (label: 'Wildberries', query: 'Wildberries'),
    (label: 'Т-Банк', query: 'Т-Банк'),
    (label: 'Альфа-Банк', query: 'Альфа'),
    (label: 'МТС', query: 'МТС'),
    (label: 'Контур', query: 'Контур'),
    (label: 'Мегафон', query: 'Мегафон'),
    (label: 'ВТБ', query: 'ВТБ'),
    (label: 'Kaspersky', query: 'Kaspersky'),
    (label: 'Lamoda', query: 'Lamoda'),
    (label: '2ГИС', query: '2ГИС'),
  ];

  static const portals = [
    'habr',
    'hirify',
    'talanto',
    'getmatch',
    'remoteok',
    'remotive',
    'himalayas',
    'jobicy',
    'arbeitnow',
    'weworkremotely',
    'workingnomads',
    'greenhouse',
    'hh',
  ];

  static const portalLabels = {
    'habr': 'Habr',
    'hirify': 'Hirify',
    'talanto': 'Talanto',
    'getmatch': 'GetMatch',
    'remoteok': 'Remote OK',
    'remotive': 'Remotive',
    'himalayas': 'Himalayas',
    'jobicy': 'Jobicy',
    'arbeitnow': 'Arbeitnow',
    'weworkremotely': 'WWR',
    'workingnomads': 'Nomads',
    'greenhouse': 'Careers',
    'hh': 'hh.ru',
  };

  @override
  void initState() {
    super.initState();
    final f = context.read<AppState>().vacancyFilters;
    qCtrl = TextEditingController(text: f.q);
    cityCtrl = TextEditingController(text: f.cities.join(', '));
    companyCtrl = TextEditingController(text: f.companies.join(', '));
    skillCtrl = TextEditingController(text: f.skills.join(', '));
    salaryFromCtrl = TextEditingController(text: f.salaryFrom?.toString() ?? '');
    salaryToCtrl = TextEditingController(text: f.salaryTo?.toString() ?? '');
  }

  @override
  void dispose() {
    qCtrl.dispose();
    cityCtrl.dispose();
    companyCtrl.dispose();
    skillCtrl.dispose();
    salaryFromCtrl.dispose();
    salaryToCtrl.dispose();
    super.dispose();
  }

  List<String> _splitCsv(String raw) =>
      raw.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();

  void _syncListCtrls(VacancyFilters f) {
    cityCtrl.text = f.cities.join(', ');
    companyCtrl.text = f.companies.join(', ');
    skillCtrl.text = f.skills.join(', ');
  }

  Future<void> _apply(AppState state) async {
    state.vacancyFilters.q = qCtrl.text;
    await state.applyVacancyFilters();
  }

  Future<void> _applyManual(AppState state) async {
    final f = state.vacancyFilters;
    f.q = qCtrl.text;
    f.cities
      ..clear()
      ..addAll(_splitCsv(cityCtrl.text));
    f.companies
      ..clear()
      ..addAll(_splitCsv(companyCtrl.text));
    f.skills
      ..clear()
      ..addAll(_splitCsv(skillCtrl.text));
    setState(() {});
    await state.applyVacancyFilters();
  }

  Future<void> _applySalary(AppState state) async {
    final f = state.vacancyFilters;
    final fromRaw = salaryFromCtrl.text.replaceAll(RegExp(r'[\s\u00a0]'), '');
    final toRaw = salaryToCtrl.text.replaceAll(RegExp(r'[\s\u00a0]'), '');
    f.salaryFrom = fromRaw.isEmpty ? null : int.tryParse(fromRaw);
    f.salaryTo = toRaw.isEmpty ? null : int.tryParse(toRaw);
    f.hasSalary = null;
    // sync back parsed values (or clear invalid)
    salaryFromCtrl.text = f.salaryFrom?.toString() ?? '';
    salaryToCtrl.text = f.salaryTo?.toString() ?? '';
    setState(() {});
    await _apply(state);
  }

  Future<void> _set(AppState state, VoidCallback mutate) async {
    mutate();
    _syncListCtrls(state.vacancyFilters);
    setState(() {});
    await _apply(state);
  }

  Future<void> _toggle(AppState state, List<String> list, String value) async {
    await _set(state, () => VacancyFilters.toggle(list, value));
  }

  int _sectionCount(VacancyFilters f, AppState state, _FilterSection s) => switch (s) {
        _FilterSection.stack => f.skills.length,
        _FilterSection.role => f.roles.length,
        _FilterSection.portal => f.sources.length,
        _FilterSection.format => f.workFormats.length,
        _FilterSection.experience => f.experiences.length,
        _FilterSection.salary => (f.salaryFrom != null ? 1 : 0) + (f.salaryTo != null ? 1 : 0),
        _FilterSection.status => f.statuses.length,
        _FilterSection.application => f.applicationStatuses.length,
        _FilterSection.sort => f.sort == 'published_at' ? 0 : 1,
        _FilterSection.age => f.maxAgeHours != null ? 1 : 0,
        _FilterSection.employment => f.employmentTypes.length,
        _FilterSection.city => f.cities.length,
        _FilterSection.company => f.companies.length,
        _FilterSection.profile => f.profileIds.length,
        _FilterSection.manual => 0,
      };

  String _sectionLabel(_FilterSection s) => switch (s) {
        _FilterSection.role => 'Роль',
        _FilterSection.stack => 'Стек',
        _FilterSection.company => 'Компания',
        _FilterSection.salary => 'Зарплата',
        _FilterSection.format => 'Формат',
        _FilterSection.experience => 'Опыт',
        _FilterSection.city => 'Город',
        _FilterSection.portal => 'Портал',
        _FilterSection.status => 'Статус',
        _FilterSection.application => 'Отклик',
        _FilterSection.employment => 'Занятость',
        _FilterSection.age => 'Возраст',
        _FilterSection.profile => 'Профиль',
        _FilterSection.sort => 'Сорт',
        _FilterSection.manual => 'Ещё',
      };

  IconData _sectionIcon(_FilterSection s) => switch (s) {
        _FilterSection.role => Icons.person_search_rounded,
        _FilterSection.stack => Icons.code_rounded,
        _FilterSection.company => Icons.apartment_rounded,
        _FilterSection.salary => Icons.payments_rounded,
        _FilterSection.format => Icons.home_work_rounded,
        _FilterSection.experience => Icons.timeline_rounded,
        _FilterSection.city => Icons.location_on_rounded,
        _FilterSection.portal => Icons.public_rounded,
        _FilterSection.status => Icons.label_rounded,
        _FilterSection.application => Icons.outgoing_mail,
        _FilterSection.employment => Icons.work_history_rounded,
        _FilterSection.age => Icons.schedule_rounded,
        _FilterSection.profile => Icons.badge_rounded,
        _FilterSection.sort => Icons.sort_rounded,
        _FilterSection.manual => Icons.edit_note_rounded,
      };

  List<_FilterSection> _visibleSections(AppState state) {
    final list = <_FilterSection>[
      _FilterSection.role,
      _FilterSection.stack,
      _FilterSection.company,
      _FilterSection.salary,
      _FilterSection.format,
      _FilterSection.experience,
      _FilterSection.city,
      _FilterSection.portal,
      _FilterSection.status,
      _FilterSection.application,
      _FilterSection.employment,
      _FilterSection.age,
      _FilterSection.sort,
    ];
    if (state.profiles.isNotEmpty) list.add(_FilterSection.profile);
    list.add(_FilterSection.manual);
    return list;
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final f = state.vacancyFilters;
    final sections = _visibleSections(state);
    final active = sections.contains(section) ? section : sections.first;

    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Лента', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
              const SizedBox(width: 8),
              if (f.activeCount > 0) _badge('${f.activeCount}'),
              const Spacer(),
              Text(
                '${state.vacancies.length} / ${state.vacanciesTotal}',
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
              ),
              IconButton(
                tooltip: state.syncing ? 'Синхронизация…' : 'Синхронизировать',
                visualDensity: VisualDensity.compact,
                onPressed: state.syncing ? null : state.syncNow,
                icon: state.syncing
                    ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.sync, size: 18, color: AppTheme.accent),
              ),
              IconButton(
                tooltip: collapsed ? 'Показать фильтры' : 'Свернуть фильтры',
                visualDensity: VisualDensity.compact,
                onPressed: () => setState(() => collapsed = !collapsed),
                icon: Icon(collapsed ? Icons.expand_more : Icons.expand_less, size: 20, color: AppTheme.muted),
              ),
              TextButton(
                style: TextButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                ),
                onPressed: () async {
                  qCtrl.clear();
                  cityCtrl.clear();
                  companyCtrl.clear();
                  skillCtrl.clear();
                  salaryFromCtrl.clear();
                  salaryToCtrl.clear();
                  await state.clearVacancyFilters();
                  setState(() {});
                },
                child: const Text('Сброс'),
              ),
            ],
          ),
          if (!collapsed) ...[
            SizedBox(
              height: 34,
              child: TextField(
                controller: qCtrl,
                style: const TextStyle(fontSize: 13),
                decoration: const InputDecoration(
                  hintText: 'поиск: компания, роль, стек',
                  prefixIcon: Icon(Icons.search, size: 18),
                  isDense: true,
                  contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                ),
                onSubmitted: (_) => _apply(state),
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: [
                for (final s in sections)
                  _tab(
                    icon: _sectionIcon(s),
                    label: _sectionLabel(s),
                    selected: active == s,
                    count: _sectionCount(f, state, s),
                    onTap: () => setState(() => section = s),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            _sectionBody(state, f, active),
          ],
        ],
      ),
    );
  }

  Widget _sectionBody(AppState state, VacancyFilters f, _FilterSection active) {
    final cityChips = state.filterCities.take(12).toList();
    final skillExtras = state.filterSkills
        .where((s) => s.length < 18 && !languages.any((l) => l.toLowerCase() == s.toLowerCase()))
        .take(10)
        .toList();

    final chips = <Widget>[];

    switch (active) {
      case _FilterSection.stack:
        for (final item in languages) {
          chips.add(FilterIconChip(
            label: item,
            selected: VacancyFilters.has(f.skills, item),
            onTap: () => _toggle(state, f.skills, item),
            logo: skillLogoFor(item),
          ));
        }
        for (final item in skillExtras) {
          chips.add(FilterIconChip(
            label: item,
            selected: VacancyFilters.has(f.skills, item),
            onTap: () => _toggle(state, f.skills, item),
            logo: skillLogoFor(item),
            icon: Icons.extension_rounded,
            iconColor: AppTheme.muted,
          ));
        }
      case _FilterSection.role:
        for (final item in roles) {
          chips.add(FilterIconChip(
            label: item,
            selected: VacancyFilters.has(f.roles, item),
            onTap: () => _toggle(state, f.roles, item),
            logo: roleLogos[item],
            icon: roleFallbackIcons[item],
          ));
        }
      case _FilterSection.portal:
        chips.add(FilterIconChip(
          label: 'Все',
          selected: f.sources.isEmpty,
          onTap: () => _set(state, () => f.sources.clear()),
          icon: Icons.select_all_rounded,
        ));
        for (final s in portals) {
          chips.add(FilterIconChip(
            label: portalLabels[s] ?? s,
            selected: VacancyFilters.has(f.sources, s),
            onTap: () => _toggle(state, f.sources, s),
            logo: portalLogos[s],
            icon: portalLogos[s] == null ? Icons.public_rounded : null,
          ));
        }
      case _FilterSection.format:
        chips.add(FilterIconChip(
          label: 'Все',
          selected: f.workFormats.isEmpty,
          onTap: () => _set(state, () => f.workFormats.clear()),
          icon: Icons.select_all_rounded,
        ));
        for (final fmt in const ['remote', 'hybrid', 'office']) {
          chips.add(FilterIconChip(
            label: fmt[0].toUpperCase() + fmt.substring(1),
            selected: VacancyFilters.has(f.workFormats, fmt),
            onTap: () => _toggle(state, f.workFormats, fmt),
            icon: formatFallbackIcons[fmt],
          ));
        }
      case _FilterSection.experience:
        chips.add(FilterIconChip(
          label: 'Любой',
          selected: f.experiences.isEmpty,
          onTap: () => _set(state, () => f.experiences.clear()),
          icon: Icons.all_inclusive_rounded,
        ));
        chips.add(FilterIconChip(
          label: 'Без опыта',
          selected: VacancyFilters.has(f.experiences, 'no_experience'),
          onTap: () => _toggle(state, f.experiences, 'no_experience'),
          icon: Icons.spa_rounded,
          iconColor: const Color(0xFF81C784),
        ));
        chips.add(FilterIconChip(
          label: '1–3',
          selected: VacancyFilters.has(f.experiences, 'between_1_and_3'),
          onTap: () => _toggle(state, f.experiences, 'between_1_and_3'),
          icon: Icons.looks_one_rounded,
        ));
        chips.add(FilterIconChip(
          label: '3–6',
          selected: VacancyFilters.has(f.experiences, 'between_3_and_6'),
          onTap: () => _toggle(state, f.experiences, 'between_3_and_6'),
          icon: Icons.looks_3_rounded,
        ));
        chips.add(FilterIconChip(
          label: '6+',
          selected: VacancyFilters.has(f.experiences, 'more_than_6'),
          onTap: () => _toggle(state, f.experiences, 'more_than_6'),
          icon: Icons.looks_6_rounded,
        ));
      case _FilterSection.salary:
        return Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(child: _salaryField(salaryFromCtrl, 'от ₽ / мес', 'без низа', () => _applySalary(state))),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8),
              child: Text('—', style: TextStyle(color: AppTheme.muted, fontWeight: FontWeight.w700, fontSize: 16)),
            ),
            Expanded(child: _salaryField(salaryToCtrl, 'до ₽ / мес', 'без верха', () => _applySalary(state))),
            const SizedBox(width: 8),
            SizedBox(
              height: 48,
              child: ElevatedButton(
                onPressed: () => _applySalary(state),
                child: const Text('OK'),
              ),
            ),
            const SizedBox(width: 6),
            SizedBox(
              height: 48,
              child: TextButton(
                onPressed: () async {
                  salaryFromCtrl.clear();
                  salaryToCtrl.clear();
                  await _set(state, () {
                    f.salaryFrom = null;
                    f.salaryTo = null;
                    f.hasSalary = null;
                  });
                },
                child: const Text('Сброс'),
              ),
            ),
          ],
        );
      case _FilterSection.status:
        chips.add(_chip('все', f.statuses.isEmpty, () => _set(state, () => f.statuses.clear())));
        for (final s in const ['new', 'matched', 'ignored']) {
          chips.add(_chip(s, VacancyFilters.has(f.statuses, s), () => _toggle(state, f.statuses, s)));
        }
      case _FilterSection.application:
        chips.add(_chip('Все', f.applicationStatuses.isEmpty, () => _set(state, () => f.applicationStatuses.clear())));
        chips.add(_chip('Подобрана', VacancyFilters.has(f.applicationStatuses, 'matched'),
            () => _toggle(state, f.applicationStatuses, 'matched')));
        chips.add(_chip('В очереди', VacancyFilters.has(f.applicationStatuses, 'queued'),
            () => _toggle(state, f.applicationStatuses, 'queued')));
        chips.add(_chip('Отклик', VacancyFilters.has(f.applicationStatuses, 'applied'),
            () => _toggle(state, f.applicationStatuses, 'applied')));
        chips.add(_chip('Dry run', VacancyFilters.has(f.applicationStatuses, 'dry_run'),
            () => _toggle(state, f.applicationStatuses, 'dry_run')));
        chips.add(_chip('Ответ', VacancyFilters.has(f.applicationStatuses, 'response'),
            () => _toggle(state, f.applicationStatuses, 'response')));
        chips.add(_chip('Интервью', VacancyFilters.has(f.applicationStatuses, 'interview'),
            () => _toggle(state, f.applicationStatuses, 'interview')));
        chips.add(_chip('Отказ', VacancyFilters.has(f.applicationStatuses, 'rejected'),
            () => _toggle(state, f.applicationStatuses, 'rejected')));
      case _FilterSection.sort:
        chips.add(_chip('Новые', f.sort == 'published_at', () => _set(state, () => f.sort = 'published_at')));
        chips.add(_chip('Зарплата ₽', f.sort == 'salary', () => _set(state, () => f.sort = 'salary')));
        chips.add(_chip('Сбор', f.sort == 'collected_at', () => _set(state, () => f.sort = 'collected_at')));
        chips.add(_chip('Название', f.sort == 'title', () => _set(state, () => f.sort = 'title')));
      case _FilterSection.age:
        chips.add(_chip('любой', f.maxAgeHours == null, () => _set(state, () => f.maxAgeHours = null)));
        chips.add(_chip('24ч', f.maxAgeHours == 24, () => _set(state, () => f.maxAgeHours = 24)));
        chips.add(_chip('3д', f.maxAgeHours == 72, () => _set(state, () => f.maxAgeHours = 72)));
        chips.add(_chip('7д', f.maxAgeHours == 168, () => _set(state, () => f.maxAgeHours = 168)));
        chips.add(_chip('14д', f.maxAgeHours == 336, () => _set(state, () => f.maxAgeHours = 336)));
        chips.add(_chip('30д', f.maxAgeHours == 720, () => _set(state, () => f.maxAgeHours = 720)));
      case _FilterSection.employment:
        chips.add(_chip('любая', f.employmentTypes.isEmpty, () => _set(state, () => f.employmentTypes.clear())));
        for (final e in const ['full', 'part', 'contract', 'intern']) {
          chips.add(_chip(e, VacancyFilters.has(f.employmentTypes, e), () => _toggle(state, f.employmentTypes, e)));
        }
      case _FilterSection.city:
        chips.add(_chip('все', f.cities.isEmpty, () => _set(state, () => f.cities.clear())));
        for (final c in cityChips) {
          chips.add(_chip(c, VacancyFilters.has(f.cities, c), () => _toggle(state, f.cities, c)));
        }
      case _FilterSection.company:
        chips.add(FilterIconChip(
          label: 'Все',
          selected: f.companies.isEmpty,
          onTap: () => _set(state, () => f.companies.clear()),
          icon: Icons.select_all_rounded,
        ));
        for (final item in featuredCompanies) {
          chips.add(FilterIconChip(
            label: item.label,
            selected: VacancyFilters.has(f.companies, item.query),
            onTap: () => _toggle(state, f.companies, item.query),
            logo: companyLogoFor(item.label),
          ));
        }
        // остальные компании — только через «Ещё» / ручной ввод, без серых заглушек
      case _FilterSection.profile:
        chips.add(_chip('все', f.profileIds.isEmpty, () => _set(state, () => f.profileIds.clear())));
        for (final p in state.profiles) {
          chips.add(_chip(p.name, f.profileIds.contains(p.id), () => _set(state, () {
            if (f.profileIds.contains(p.id)) {
              f.profileIds.remove(p.id);
            } else {
              f.profileIds.add(p.id);
            }
          })));
        }
      case _FilterSection.manual:
        return Row(
          children: [
            Expanded(child: _field(cityCtrl, 'Города через запятую', () => _applyManual(state))),
            const SizedBox(width: 6),
            Expanded(child: _field(companyCtrl, 'Компании через запятую', () => _applyManual(state))),
            const SizedBox(width: 6),
            Expanded(child: _field(skillCtrl, 'Стек через запятую', () => _applyManual(state))),
            const SizedBox(width: 6),
            SizedBox(
              height: 34,
              child: ElevatedButton(
                onPressed: () => _applyManual(state),
                child: const Text('OK'),
              ),
            ),
          ],
        );
    }

    return Wrap(spacing: 4, runSpacing: 4, children: chips);
  }

  Widget _tab({
    required IconData icon,
    required String label,
    required bool selected,
    required int count,
    required VoidCallback onTap,
  }) {
    final r = FilterIconChip.radius;
    return Align(
      alignment: Alignment.centerLeft,
      widthFactor: 1,
      child: Material(
        color: selected ? AppTheme.accent.withValues(alpha: 0.2) : AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(r),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(r),
          child: Container(
            height: FilterIconChip.height,
            padding: const EdgeInsets.symmetric(horizontal: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(r),
              border: Border.all(color: selected ? AppTheme.accent : AppTheme.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Icon(icon, size: 16, color: selected ? AppTheme.accent : AppTheme.textSecondary),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12.5,
                    height: 1.1,
                    letterSpacing: 0.1,
                    fontWeight: FontWeight.w700,
                    color: selected ? AppTheme.accent : AppTheme.textSecondary,
                  ),
                ),
                if (count > 0) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.accent.withValues(alpha: 0.25),
                      borderRadius: BorderRadius.circular(r),
                    ),
                    child: Text(
                      '$count',
                      style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: AppTheme.accent),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _chip(String label, bool selected, VoidCallback onTap, {IconData? icon, Color? iconColor}) {
    return FilterIconChip(
      label: label,
      selected: selected,
      onTap: onTap,
      icon: icon,
      iconColor: iconColor,
    );
  }

  Widget _badge(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: AppTheme.accent.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(text, style: const TextStyle(color: AppTheme.accent, fontSize: 11, fontWeight: FontWeight.w700)),
    );
  }

  Widget _salaryField(
    TextEditingController ctrl,
    String label,
    String hint,
    VoidCallback onSubmit,
  ) {
    return SizedBox(
      height: 48,
      child: TextField(
        controller: ctrl,
        keyboardType: TextInputType.number,
        inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9\s]'))],
        style: const TextStyle(fontSize: 14, height: 1.2),
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          floatingLabelBehavior: FloatingLabelBehavior.always,
          isDense: false,
          contentPadding: const EdgeInsets.fromLTRB(12, 18, 12, 12),
          filled: true,
          fillColor: AppTheme.surfaceAlt,
        ),
        onSubmitted: (_) => onSubmit(),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String label, VoidCallback onSubmit) {
    return SizedBox(
      height: 48,
      child: TextField(
        controller: ctrl,
        style: const TextStyle(fontSize: 13, height: 1.2),
        decoration: InputDecoration(
          labelText: label,
          floatingLabelBehavior: FloatingLabelBehavior.always,
          isDense: false,
          contentPadding: const EdgeInsets.fromLTRB(12, 18, 12, 12),
          filled: true,
          fillColor: AppTheme.surfaceAlt,
        ),
        onSubmitted: (_) => onSubmit(),
      ),
    );
  }
}
