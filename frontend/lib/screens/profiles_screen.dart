import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../theme/app_theme.dart';

class ProfilesScreen extends StatelessWidget {
  const ProfilesScreen({super.key});

  Future<void> _create(BuildContext context) async {
    final nameCtrl = TextEditingController(text: 'Python Backend');
    final skillsCtrl = TextEditingController(text: 'Python, FastAPI, PostgreSQL');
    final excludeCtrl = TextEditingController(text: 'PHP, Bitrix');
    final rolesCtrl = TextEditingController(text: 'Backend, Python Developer');
    final salaryFromCtrl = TextEditingController(text: '180000');
    final salaryToCtrl = TextEditingController(text: '400000');
    final citiesCtrl = TextEditingController(text: 'Москва, Любой');
    var remote = true;
    var hybrid = true;
    var office = false;
    var exp13 = true;
    var exp36 = true;
    var srcHabr = true;
    var srcHirify = true;
    var srcTalanto = true;
    var srcGetmatch = true;
    var maxAge = 168;

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setLocal) => AlertDialog(
          backgroundColor: AppTheme.surface,
          title: const Text('Новый Search Profile'),
          content: SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Название')),
                  TextField(controller: rolesCtrl, decoration: const InputDecoration(labelText: 'Роли')),
                  TextField(controller: skillsCtrl, decoration: const InputDecoration(labelText: 'Include skills')),
                  TextField(controller: excludeCtrl, decoration: const InputDecoration(labelText: 'Exclude skills')),
                  TextField(controller: salaryFromCtrl, decoration: const InputDecoration(labelText: 'Зарплата от')),
                  TextField(controller: salaryToCtrl, decoration: const InputDecoration(labelText: 'Зарплата до')),
                  TextField(controller: citiesCtrl, decoration: const InputDecoration(labelText: 'Города')),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: [
                      FilterChip(label: const Text('Remote'), selected: remote, onSelected: (v) => setLocal(() => remote = v)),
                      FilterChip(label: const Text('Hybrid'), selected: hybrid, onSelected: (v) => setLocal(() => hybrid = v)),
                      FilterChip(label: const Text('Office'), selected: office, onSelected: (v) => setLocal(() => office = v)),
                      FilterChip(label: const Text('1–3 года'), selected: exp13, onSelected: (v) => setLocal(() => exp13 = v)),
                      FilterChip(label: const Text('3–6 лет'), selected: exp36, onSelected: (v) => setLocal(() => exp36 = v)),
                    ],
                  ),
                  Wrap(
                    spacing: 8,
                    children: [
                      FilterChip(label: const Text('Habr'), selected: srcHabr, onSelected: (v) => setLocal(() => srcHabr = v)),
                      FilterChip(label: const Text('Hirify'), selected: srcHirify, onSelected: (v) => setLocal(() => srcHirify = v)),
                      FilterChip(label: const Text('Talanto'), selected: srcTalanto, onSelected: (v) => setLocal(() => srcTalanto = v)),
                      FilterChip(label: const Text('GetMatch'), selected: srcGetmatch, onSelected: (v) => setLocal(() => srcGetmatch = v)),
                    ],
                  ),
                  InputDecorator(
                    decoration: const InputDecoration(labelText: 'Возраст вакансии', isDense: true),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<int>(
                        isExpanded: true,
                        value: maxAge,
                        items: const [
                          DropdownMenuItem(value: 24, child: Text('не старше 24 часов')),
                          DropdownMenuItem(value: 72, child: Text('не старше 3 дней')),
                          DropdownMenuItem(value: 168, child: Text('не старше 7 дней')),
                          DropdownMenuItem(value: 720, child: Text('не старше 30 дней')),
                        ],
                        onChanged: (v) => setLocal(() => maxAge = v ?? 168),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
            ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Создать')),
          ],
        ),
      ),
    );

    if (ok == true && context.mounted) {
      final formats = <String>[
        if (remote) 'remote',
        if (hybrid) 'hybrid',
        if (office) 'office',
      ];
      final experience = <String>[
        if (exp13) 'between_1_and_3',
        if (exp36) 'between_3_and_6',
      ];
      final sources = <String>[
        if (srcHabr) 'habr',
        if (srcHirify) 'hirify',
        if (srcTalanto) 'talanto',
        if (srcGetmatch) 'getmatch',
      ];
      final state = context.read<AppState>();
      await state.createProfile({
        'name': nameCtrl.text.trim(),
        'include_skills': skillsCtrl.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList(),
        'exclude_skills': excludeCtrl.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList(),
        'roles': rolesCtrl.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList(),
        'salary_from': int.tryParse(salaryFromCtrl.text.trim()),
        'salary_to': int.tryParse(salaryToCtrl.text.trim()),
        'currency': 'RUB',
        'cities': citiesCtrl.text.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList(),
        'work_formats': formats,
        'experience_levels': experience,
        'sources': sources,
        'max_age_hours': maxAge,
        'is_active': true,
        'auto_apply_enabled': false,
        'daily_apply_limit': 30,
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Row(
          children: [
            Text('Search Profiles', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
            const Spacer(),
            ElevatedButton.icon(
              onPressed: () => _create(context),
              icon: const Icon(Icons.add),
              label: const Text('Создать'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        ...state.profiles.map((p) {
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(p.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Text('Skills: ${(p.includeSkills ?? []).join(", ")}', style: const TextStyle(color: AppTheme.textSecondary)),
                Text('Roles: ${(p.roles ?? []).join(", ")}', style: const TextStyle(color: AppTheme.textSecondary)),
                Text('Salary from: ${p.salaryFrom ?? "—"}', style: const TextStyle(color: AppTheme.textSecondary)),
                Text('Sources: ${(p.sources ?? []).join(", ")}', style: const TextStyle(color: AppTheme.textSecondary)),
                Text(
                  'Auto Apply: ${p.autoApplyEnabled ? "ON" : "OFF"} · Daily limit: ${p.dailyApplyLimit}',
                  style: TextStyle(color: p.autoApplyEnabled ? AppTheme.warning : AppTheme.muted),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Auto Apply для профиля'),
                  value: p.autoApplyEnabled,
                  onChanged: (v) => state.updateProfile(p.id, {'auto_apply_enabled': v}),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
}
