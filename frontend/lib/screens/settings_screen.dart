import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final intervalCtrl = TextEditingController();
  final dailyCtrl = TextEditingController();
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
          const SizedBox(height: 8),
          Text('Timezone: ${s?.timezone ?? "Europe/Moscow"}', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 12),
          ElevatedButton(
            onPressed: () => state.updateSettings({
              'sync_interval_minutes': int.tryParse(intervalCtrl.text.trim()) ?? 60,
            }),
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
