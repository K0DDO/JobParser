import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../core/msk_time.dart';
import '../theme/app_theme.dart';

class LogsScreen extends StatelessWidget {
  const LogsScreen({super.key});

  Color _levelColor(String level) => switch (level) {
        'error' => AppTheme.danger,
        'warning' => AppTheme.warning,
        'success' => AppTheme.success,
        _ => AppTheme.textSecondary,
      };

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return RefreshIndicator(
      onRefresh: state.loadLogs,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text('System Logs', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 16),
          ...state.logs.map((log) {
            final time = MskTime.format(log.createdAt, 'HH:mm:ss');
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: RichText(
                text: TextSpan(
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 13, color: AppTheme.textPrimary),
                  children: [
                    TextSpan(text: '[$time] ', style: TextStyle(color: _levelColor(log.level))),
                    TextSpan(text: '${log.category}: ', style: const TextStyle(color: AppTheme.accent)),
                    TextSpan(text: log.message),
                  ],
                ),
              ),
            );
          }),
        ],
      ),
    );
  }
}
