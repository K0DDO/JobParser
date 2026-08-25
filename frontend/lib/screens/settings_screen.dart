import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../theme/app_theme.dart';

const _lookbackOptions = <(int days, String label)>[
  (1, 'За сутки'),
  (3, 'За 3 дня'),
  (7, 'За неделю'),
  (14, 'За 2 недели'),
  (30, 'За месяц'),
];

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final intervalCtrl = TextEditingController();
  final dailyCtrl = TextEditingController();
  int _lookbackDays = 7;
  bool _seeded = false;

  @override
  void dispose() {
    intervalCtrl.dispose();
    dailyCtrl.dispose();
    super.dispose();
  }

  void _seedIfNeeded(AppState state) {
    if (_seeded || state.settings == null) return;
    intervalCtrl.text = '${state.settings!.syncIntervalMinutes}';
    dailyCtrl.text = '${state.settings!.globalDailyLimit}';
    _lookbackDays = state.settings!.syncLookbackDays;
    _seeded = true;
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    _seedIfNeeded(state);
    final s = state.settings;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Настройки', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 20),
        _section('General', [
          TextField(
            controller: intervalCtrl,
            decoration: const InputDecoration(labelText: 'Sync interval (minutes)'),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 12),
          Text('Период выгрузки при синке', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 4),
          Text(
            'Берутся вакансии, опубликованные за выбранный промежуток (по умолчанию неделя).',
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<int>(
            value: _lookbackOptions.any((e) => e.$1 == _lookbackDays) ? _lookbackDays : 7,
            decoration: const InputDecoration(labelText: 'Lookback'),
            items: [
              for (final opt in _lookbackOptions)
                DropdownMenuItem(value: opt.$1, child: Text(opt.$2)),
            ],
            onChanged: (v) {
              if (v == null) return;
              setState(() => _lookbackDays = v);
            },
          ),
          const SizedBox(height: 8),
          Text('Timezone: ${s?.timezone ?? "Europe/Moscow"}', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: () async {
              final prevLookback = state.settings?.syncLookbackDays ?? 7;
              await state.updateSettings({
                'sync_interval_minutes': int.tryParse(intervalCtrl.text.trim()) ?? 60,
                'sync_lookback_days': _lookbackDays,
              });
              if (_lookbackDays != prevLookback) {
                state.vacancyFilters.maxAgeHours = _lookbackDays * 24;
                await state.applyVacancyFilters();
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        'Период синка: ${_lookbackOptions.firstWhere((e) => e.$1 == _lookbackDays).$2}. '
                        'Запускаю синхронизацию…',
                      ),
                    ),
                  );
                }
                await state.syncNow();
              }
            },
            child: const Text('Сохранить General'),
          ),
        ]),
        const SizedBox(height: 16),
        _section('Auto Apply', [
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Dry Run'),
            subtitle: const Text('Показывать желаемые отклики без реальной отправки'),
            value: s?.dryRun ?? true,
            onChanged: (v) => state.updateSettings({'dry_run': v}),
          ),
          TextField(
            controller: dailyCtrl,
            decoration: const InputDecoration(labelText: 'Global daily limit'),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 8),
          Text(
            'Global Auto Apply: ${(s?.globalAutoApply ?? false) ? "ON" : "OFF"}',
            style: TextStyle(color: (s?.globalAutoApply ?? false) ? AppTheme.warning : AppTheme.muted),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: [
              ElevatedButton(
                onPressed: () => state.updateSettings({
                  'global_daily_limit': int.tryParse(dailyCtrl.text.trim()) ?? 50,
                }),
                child: const Text('Сохранить лимит'),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger),
                onPressed: state.emergencyStop,
                child: const Text('Emergency Stop'),
              ),
            ],
          ),
        ]),
      ],
    );
  }

  Widget _section(String title, List<Widget> children) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}
