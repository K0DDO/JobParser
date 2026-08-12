import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../core/msk_time.dart';
import '../theme/app_theme.dart';
import '../widgets/stat_tile.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  String _fmt(DateTime? dt) => '${MskTime.format(dt)} МСК';

  Future<void> _confirmEnable(BuildContext context, AppState state) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surface,
        title: const Text('Автоотклики выключены'),
        content: const Text(
          'После включения приложение сможет автоматически отправлять отклики '
          'на вакансии, соответствующие вашим правилам.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Включить автоотклики'),
          ),
        ],
      ),
    );
    if (ok == true) await state.enableAutoApply();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final s = state.stats;

    return RefreshIndicator(
      onRefresh: state.refreshAll,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Row(
            children: [
              Text('Dashboard', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
              const Spacer(),
              if (state.loading || state.syncing)
                const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
          if (state.error != null) ...[
            const SizedBox(height: 12),
            Text(state.error!, style: const TextStyle(color: AppTheme.danger)),
          ],
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              StatTile(label: 'Всего найдено', value: '${s?.totalVacancies ?? 0}'),
              StatTile(label: 'Новых сегодня', value: '${s?.newToday ?? 0}'),
              StatTile(label: 'Подходящих', value: '${s?.matched ?? 0}'),
              StatTile(label: 'Откликов', value: '${s?.applications ?? 0}'),
              StatTile(label: 'Ответов', value: '${s?.responses ?? 0}'),
              StatTile(label: 'Интервью', value: '${s?.interviews ?? 0}'),
              StatTile(label: 'Офферов', value: '${s?.offers ?? 0}'),
              StatTile(label: 'Очередь', value: '${s?.queuePending ?? 0}'),
            ],
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.border),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _kv('Последняя синхронизация', _fmt(s?.lastSyncAt)),
                _kv('Следующая синхронизация', _fmt(s?.nextSyncAt)),
                _kv('Статус', s?.systemStatus == 'ok' ? '● Система работает' : '● ${s?.systemStatus ?? "—"}'),
                _kv(
                  'Автоотклики',
                  (s?.globalAutoApply ?? false) ? '● ВКЛЮЧЕНЫ' : '● ВЫКЛЮЧЕНЫ',
                  valueColor: (s?.globalAutoApply ?? false) ? AppTheme.warning : AppTheme.muted,
                ),
                _kv('Dry Run', (s?.dryRun ?? true) ? 'ON' : 'OFF'),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    ElevatedButton.icon(
                      onPressed: state.syncing ? null : state.syncNow,
                      icon: const Icon(Icons.sync),
                      label: Text(state.syncing ? 'Синхронизация…' : 'Синхронизировать сейчас'),
                    ),
                    if (s?.globalAutoApply != true)
                      OutlinedButton(
                        onPressed: () => _confirmEnable(context, state),
                        child: const Text('Включить автоотклики'),
                      )
                    else
                      OutlinedButton(
                        onPressed: state.disableAutoApply,
                        child: const Text('Выключить автоотклики'),
                      ),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.danger),
                      onPressed: state.emergencyStop,
                      child: const Text('Emergency Stop'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _kv(String k, String v, {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          SizedBox(width: 220, child: Text(k, style: const TextStyle(color: AppTheme.textSecondary))),
          Expanded(child: Text(v, style: TextStyle(color: valueColor ?? AppTheme.textPrimary, fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}
