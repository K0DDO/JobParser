import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../core/vacancy_filters.dart';
import '../theme/app_theme.dart';

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
  bool extra = false;
  bool collapsed = false;

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

  @override
  void initState() {
    super.initState();
    final f = context.read<AppState>().vacancyFilters;
    qCtrl = TextEditingController(text: f.q);
    cityCtrl = TextEditingController(text: f.cities.join(', '));
    companyCtrl = TextEditingController(text: f.company ?? '');
    skillCtrl = TextEditingController(text: f.skills.join(', '));
  }

  @override
  void dispose() {
    qCtrl.dispose();
    cityCtrl.dispose();
    companyCtrl.dispose();
    skillCtrl.dispose();
    super.dispose();
  }

  Future<void> _apply(AppState state) async {
    final f = state.vacancyFilters;
    f.q = qCtrl.text;
    f.company = companyCtrl.text.trim().isEmpty ? null : companyCtrl.text.trim();

    final typedCities = cityCtrl.text
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    for (final c in typedCities) {
      if (!VacancyFilters.has(f.cities, c)) f.cities.add(c);
    }

    final typedSkills = skillCtrl.text
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    for (final s in typedSkills) {
      if (!VacancyFilters.has(f.skills, s)) f.skills.add(s);
    }

    await state.applyVacancyFilters();
  }

  Future<void> _set(AppState state, VoidCallback mutate) async {
    mutate();
    setState(() {});
    await _apply(state);
  }

  Future<void> _toggle(AppState state, List<String> list, String value) async {
    await _set(state, () => VacancyFilters.toggle(list, value));
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final f = state.vacancyFilters;
    final cityChips = state.filterCities.take(12).toList();
    final skillExtras = state.filterSkills
        .where((s) => s.length < 18 && !languages.any((l) => l.toLowerCase() == s.toLowerCase()))
        .take(10)
        .toList();

    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 6),
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
              const SizedBox(width: 4),
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
            _row('Стек', [
              for (final item in languages)
                _chip(item, VacancyFilters.has(f.skills, item), () async {
                  await _toggle(state, f.skills, item);
                  skillCtrl.text = f.skills.join(', ');
                }),
              for (final item in skillExtras)
                _chip(item, VacancyFilters.has(f.skills, item), () async {
                  await _toggle(state, f.skills, item);
                  skillCtrl.text = f.skills.join(', ');
                }),
            ]),
            _row('Роль', [
              for (final item in roles)
                _chip(item, VacancyFilters.has(f.roles, item), () => _toggle(state, f.roles, item)),
            ]),
            _row('Портал', [
              _chip('Все', f.sources.isEmpty, () => _set(state, () => f.sources.clear())),
              for (final s in const ['habr', 'hirify', 'talanto', 'getmatch', 'hh'])
                _chip(s, VacancyFilters.has(f.sources, s), () => _toggle(state, f.sources, s)),
            ]),
            _row('Формат', [
              _chip('Все', f.workFormats.isEmpty, () => _set(state, () => f.workFormats.clear())),
              for (final fmt in const ['remote', 'hybrid', 'office'])
                _chip(
                  fmt[0].toUpperCase() + fmt.substring(1),
                  VacancyFilters.has(f.workFormats, fmt),
                  () => _toggle(state, f.workFormats, fmt),
                ),
            ]),
            _row('Опыт', [
              _chip('Любой', f.experiences.isEmpty, () => _set(state, () => f.experiences.clear())),
              _chip('Без опыта', VacancyFilters.has(f.experiences, 'no_experience'),
                  () => _toggle(state, f.experiences, 'no_experience')),
              _chip('1–3', VacancyFilters.has(f.experiences, 'between_1_and_3'),
                  () => _toggle(state, f.experiences, 'between_1_and_3')),
              _chip('3–6', VacancyFilters.has(f.experiences, 'between_3_and_6'),
                  () => _toggle(state, f.experiences, 'between_3_and_6')),
              _chip('6+', VacancyFilters.has(f.experiences, 'more_than_6'),
                  () => _toggle(state, f.experiences, 'more_than_6')),
            ]),
            _row('₽ / мес', [
              _chip('любая', f.salaryFrom == null && f.salaryTo == null, () => _set(state, () {
                f.salaryFrom = null;
                f.salaryTo = null;
              })),
              for (final v in const [100000, 150000, 180000, 200000, 250000, 300000, 400000])
                _chip('от ${v ~/ 1000}к', f.salaryFrom == v, () => _set(state, () {
                  f.salaryFrom = f.salaryFrom == v ? null : v;
                })),
              _chip('до 200к', f.salaryTo == 200000, () => _set(state, () {
                f.salaryTo = f.salaryTo == 200000 ? null : 200000;
              })),
              _chip('до 300к', f.salaryTo == 300000, () => _set(state, () {
                f.salaryTo = f.salaryTo == 300000 ? null : 300000;
              })),
              _chip('есть вилка', f.hasSalary == true, () => _set(state, () => f.hasSalary = f.hasSalary == true ? null : true)),
              _chip('без вилки', f.hasSalary == false, () => _set(state, () => f.hasSalary = f.hasSalary == false ? null : false)),
            ]),
            _row('Статус', [
              _chip('все', f.statuses.isEmpty, () => _set(state, () => f.statuses.clear())),
              for (final s in const ['new', 'matched', 'ignored'])
                _chip(s, VacancyFilters.has(f.statuses, s), () => _toggle(state, f.statuses, s)),
            ]),
            _row('Отклик', [
              _chip('Все', f.applicationStatuses.isEmpty, () => _set(state, () => f.applicationStatuses.clear())),
              _chip('Подобрана', VacancyFilters.has(f.applicationStatuses, 'matched'),
                  () => _toggle(state, f.applicationStatuses, 'matched')),
              _chip('В очереди', VacancyFilters.has(f.applicationStatuses, 'queued'),
                  () => _toggle(state, f.applicationStatuses, 'queued')),
              _chip('Отклик', VacancyFilters.has(f.applicationStatuses, 'applied'),
                  () => _toggle(state, f.applicationStatuses, 'applied')),
              _chip('Dry run', VacancyFilters.has(f.applicationStatuses, 'dry_run'),
                  () => _toggle(state, f.applicationStatuses, 'dry_run')),
              _chip('Ответ', VacancyFilters.has(f.applicationStatuses, 'response'),
                  () => _toggle(state, f.applicationStatuses, 'response')),
              _chip('Интервью', VacancyFilters.has(f.applicationStatuses, 'interview'),
                  () => _toggle(state, f.applicationStatuses, 'interview')),
              _chip('Отказ', VacancyFilters.has(f.applicationStatuses, 'rejected'),
                  () => _toggle(state, f.applicationStatuses, 'rejected')),
            ]),
            _row('Сорт', [
              _chip('Новые', f.sort == 'published_at', () => _set(state, () => f.sort = 'published_at')),
              _chip('Зарплата ₽', f.sort == 'salary', () => _set(state, () => f.sort = 'salary')),
              _chip('Сбор', f.sort == 'collected_at', () => _set(state, () => f.sort = 'collected_at')),
              _chip('Название', f.sort == 'title', () => _set(state, () => f.sort = 'title')),
            ]),
            _row('Возраст', [
              _chip('любой', f.maxAgeHours == null, () => _set(state, () => f.maxAgeHours = null)),
              _chip('24ч', f.maxAgeHours == 24, () => _set(state, () => f.maxAgeHours = 24)),
              _chip('3д', f.maxAgeHours == 72, () => _set(state, () => f.maxAgeHours = 72)),
              _chip('7д', f.maxAgeHours == 168, () => _set(state, () => f.maxAgeHours = 168)),
              _chip('14д', f.maxAgeHours == 336, () => _set(state, () => f.maxAgeHours = 336)),
              _chip('30д', f.maxAgeHours == 720, () => _set(state, () => f.maxAgeHours = 720)),
            ]),
            _row('Занятость', [
              _chip('любая', f.employmentTypes.isEmpty, () => _set(state, () => f.employmentTypes.clear())),
              for (final e in const ['full', 'part', 'contract', 'intern'])
                _chip(e, VacancyFilters.has(f.employmentTypes, e), () => _toggle(state, f.employmentTypes, e)),
            ]),
            if (cityChips.isNotEmpty)
              _row('Город', [
                _chip('все', f.cities.isEmpty, () => _set(state, () {
                  f.cities.clear();
                  cityCtrl.clear();
                })),
                for (final c in cityChips)
                  _chip(c, VacancyFilters.has(f.cities, c), () async {
                    await _toggle(state, f.cities, c);
                    cityCtrl.text = f.cities.join(', ');
                  }),
              ]),
            if (state.profiles.isNotEmpty)
              _row('Профиль', [
                _chip('все', f.profileIds.isEmpty, () => _set(state, () => f.profileIds.clear())),
                for (final p in state.profiles)
                  _chip(p.name, f.profileIds.contains(p.id), () => _set(state, () {
                    if (f.profileIds.contains(p.id)) {
                      f.profileIds.remove(p.id);
                    } else {
                      f.profileIds.add(p.id);
                    }
                  })),
              ]),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact, padding: EdgeInsets.zero),
                onPressed: () => setState(() => extra = !extra),
                child: Text(
                  extra ? 'Скрыть ручной ввод' : 'Ручной ввод: город / компания / стек',
                  style: const TextStyle(fontSize: 12, color: AppTheme.accent),
                ),
              ),
            ),
            if (extra)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Expanded(child: _field(cityCtrl, 'Города через запятую', () => _apply(state))),
                    const SizedBox(width: 6),
                    Expanded(child: _field(companyCtrl, 'Компания', () => _apply(state))),
                    const SizedBox(width: 6),
                    Expanded(child: _field(skillCtrl, 'Стек через запятую', () => _apply(state))),
                    const SizedBox(width: 6),
                    SizedBox(
                      height: 34,
                      child: ElevatedButton(
                        onPressed: () => _apply(state),
                        child: const Text('OK'),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }

  Widget _row(String label, List<Widget> chips) {
    return Padding(
      padding: const EdgeInsets.only(top: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 68,
            child: Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                label.toUpperCase(),
                style: const TextStyle(
                  fontSize: 9.5,
                  letterSpacing: 0.4,
                  color: AppTheme.muted,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
          Expanded(child: Wrap(spacing: 3, runSpacing: 3, children: chips)),
        ],
      ),
    );
  }

  Widget _chip(String label, bool selected, VoidCallback onTap) {
    return Material(
      color: selected ? AppTheme.accent.withValues(alpha: 0.18) : AppTheme.chip,
      borderRadius: BorderRadius.circular(5),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(5),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(5),
            border: Border.all(color: selected ? AppTheme.accent : AppTheme.border),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 11.5,
              height: 1.1,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              color: selected ? AppTheme.accent : AppTheme.textPrimary,
            ),
          ),
        ),
      ),
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

  Widget _field(TextEditingController ctrl, String label, VoidCallback onSubmit) {
    return SizedBox(
      height: 34,
      child: TextField(
        controller: ctrl,
        style: const TextStyle(fontSize: 12),
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        ),
        onSubmitted: (_) => onSubmit(),
      ),
    );
  }
}
