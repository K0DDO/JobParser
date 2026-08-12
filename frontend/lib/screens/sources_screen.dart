import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/msk_time.dart';
import '../theme/app_theme.dart';

class SourcesScreen extends StatelessWidget {
  const SourcesScreen({super.key});

  Color _statusColor(String s) => switch (s) {
        'ready' => AppTheme.success,
        'unavailable' => AppTheme.muted,
        'error' => AppTheme.danger,
        _ => AppTheme.warning,
      };

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Источники', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        const Text(
          'Импорт вакансий идёт с публичных API. Аккаунты на Habr / Hirify / Talanto / GetMatch для сбора не нужны. '
          'HH — только официальный OAuth после одобрения приложения. Регистрироваться и логиниться за тебя приложение не будет.',
          style: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
        ),
        const SizedBox(height: 16),
        ...state.sources.map((s) {
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
                Row(
                  children: [
                    Text(s.displayName, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                    const SizedBox(width: 10),
                    Text('● ${s.status}', style: TextStyle(color: _statusColor(s.status))),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Последняя синхронизация: ${s.lastSyncAt == null ? "—" : "${MskTime.format(s.lastSyncAt)} МСК"}',
                  style: const TextStyle(color: AppTheme.textSecondary),
                ),
                Text('Найдено сегодня: ${s.foundToday}', style: const TextStyle(color: AppTheme.textSecondary)),
                if (s.lastError != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(s.lastError!, style: const TextStyle(color: AppTheme.danger, fontSize: 12)),
                  ),
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Парсинг'),
                  value: s.parsingEnabled,
                  onChanged: (v) => state.updateSource(s.id, {'parsing_enabled': v}),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    s.autoApplySupported ? 'Автоотклики' : 'Автоотклики (не поддерживаются)',
                  ),
                  value: s.autoApplyEnabled,
                  onChanged: s.autoApplySupported
                      ? (v) => state.updateSource(s.id, {'auto_apply_enabled': v})
                      : null,
                ),
                if (s.name == 'hh') ...[
                  const SizedBox(height: 8),
                  Text(
                    s.connected ? 'HH OAuth: подключён' : 'HH OAuth: не подключён (заявка ещё на модерации)',
                    style: TextStyle(color: s.connected ? AppTheme.success : AppTheme.warning),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: () => launchUrl(
                      Uri.parse('${state.api.baseUrl}/auth/hh/login'),
                      mode: LaunchMode.externalApplication,
                    ),
                    child: const Text('Подключить HH'),
                  ),
                ],
              ],
            ),
          );
        }),
      ],
    );
  }
}
