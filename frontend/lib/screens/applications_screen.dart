import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../core/msk_time.dart';
import '../theme/app_theme.dart';

class ApplicationsScreen extends StatelessWidget {
  const ApplicationsScreen({super.key});

  static const columns = [
    ('matched', 'Новые'),
    ('queued', 'В очереди'),
    ('applied', 'Отклик'),
    ('dry_run', 'Dry Run'),
    ('response', 'Ответ'),
    ('interview', 'Интервью'),
    ('test_task', 'Тестовое'),
    ('offer', 'Оффер'),
    ('rejected', 'Отклонён'),
    ('failed', 'Ошибка'),
  ];

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text('Отклики', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 16),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (final col in columns)
                Container(
                  width: 260,
                  margin: const EdgeInsets.only(right: 12),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(col.$2, style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 10),
                      ...state.applications.where((a) => a.status == col.$1).map((a) {
                        return Container(
                          width: double.infinity,
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceAlt,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(a.vacancyTitle ?? 'Vacancy #${a.vacancyId}',
                                  style: const TextStyle(fontWeight: FontWeight.w600)),
                              Text(a.vacancyCompany ?? '—', style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                              Text((a.vacancySource ?? '').toUpperCase(),
                                  style: const TextStyle(color: AppTheme.accent, fontSize: 11)),
                              if (a.appliedAt != null)
                                Text(
                                  'Отклик: ${MskTime.format(a.appliedAt, 'dd.MM.yyyy HH:mm')} МСК',
                                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                                ),
                              if (a.isDryRun)
                                const Text('DRY RUN', style: TextStyle(color: AppTheme.warning, fontSize: 11)),
                              const SizedBox(height: 6),
                              PopupMenuButton<String>(
                                onSelected: (status) => state.updateApplicationStatus(a.id, status),
                                itemBuilder: (_) => [
                                  for (final c in columns)
                                    PopupMenuItem(value: c.$1, child: Text(c.$2)),
                                ],
                                child: const Text('Сменить статус', style: TextStyle(fontSize: 12, color: AppTheme.accent)),
                              ),
                            ],
                          ),
                        );
                      }),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
