import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/app_state.dart';
import '../core/msk_time.dart';
import '../models/models.dart';
import '../theme/app_theme.dart';
import '../widgets/vacancy_filters_bar.dart';

class VacanciesScreen extends StatelessWidget {
  const VacanciesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Column(
      children: [
        const VacancyFiltersBar(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: state.loadVacancies,
            child: state.vacancies.isEmpty
                ? ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: const [
                      SizedBox(height: 80),
                      Center(
                        child: Text(
                          'Нет вакансий по текущим фильтрам',
                          style: TextStyle(color: AppTheme.textSecondary),
                        ),
                      ),
                    ],
                  )
                : LayoutBuilder(
                    builder: (context, constraints) {
                      final cols = constraints.maxWidth >= 1400
                          ? 4
                          : constraints.maxWidth >= 1040
                              ? 3
                              : constraints.maxWidth >= 700
                                  ? 2
                                  : 1;
                      return GridView.builder(
                        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: cols,
                          mainAxisSpacing: 8,
                          crossAxisSpacing: 8,
                          mainAxisExtent: cols == 1 ? 148 : 152,
                        ),
                        itemCount: state.vacancies.length,
                        itemBuilder: (context, i) => _VacancyCard(vacancy: state.vacancies[i]),
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }
}

class _VacancyCard extends StatelessWidget {
  const _VacancyCard({required this.vacancy});

  final Vacancy vacancy;

  static final _fmt = NumberFormat.decimalPattern('ru');

  String _money(int n) {
    if (n >= 1000000) {
      final v = n / 1000000;
      final s = (v == v.roundToDouble()) ? '${v.toInt()}' : v.toStringAsFixed(1);
      return '$s млн';
    }
    if (n >= 1000 && n % 1000 == 0) {
      return '${n ~/ 1000}к';
    }
    return _fmt.format(n);
  }

  String _salary() {
    if (vacancy.salaryFrom == null && vacancy.salaryTo == null) return 'вилка не указана';
    final from = vacancy.salaryFrom;
    final to = vacancy.salaryTo;
    final orig = vacancy.originalCurrency;
    final note = (orig != null && orig != 'RUB' && orig != 'RUR') ? ' · $orig' : '';
    if (from != null && to != null) {
      return '${_money(from)} – ${_money(to)} ₽ / мес$note';
    }
    if (from != null) return 'от ${_money(from)} ₽ / мес$note';
    return 'до ${_money(to!)} ₽ / мес$note';
  }

  String _exp() => switch (vacancy.experience) {
        'no_experience' => 'без опыта',
        'between_1_and_3' => '1–3 г.',
        'between_3_and_6' => '3–6 л.',
        'more_than_6' => '6+',
        'unknown' => '',
        _ => vacancy.experience,
      };

  String _age() => MskTime.ageLabel(vacancy.publishedAt);

  Color _statusColor(String? s) => switch (s) {
        'new' => AppTheme.success,
        'applied' || 'dry_run' => AppTheme.accent,
        'response' || 'viewed' || 'interview' || 'matched' => AppTheme.accentAlt,
        'rejected' || 'failed' => AppTheme.danger,
        'ignored' => AppTheme.muted,
        _ => AppTheme.warning,
      };

  @override
  Widget build(BuildContext context) {
    final state = context.read<AppState>();
    final status = vacancy.applicationStatus ?? vacancy.status;
    final color = _statusColor(status);
    final sourceColor = AppTheme.sourceColor(vacancy.source);
    final skills = (vacancy.skills ?? []).take(5).toList();
    final meta = [
      vacancy.company ?? '—',
      vacancy.city ?? (vacancy.remote ? 'Remote' : vacancy.workFormat),
      if (_age().isNotEmpty) _age(),
      if (_exp().isNotEmpty) _exp(),
    ].join(' · ');

    return Container(
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (skills.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                skills.join('  ·  '),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 10.5, color: AppTheme.textSecondary, height: 1.1),
              ),
            ),
          Text(
            vacancy.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, height: 1.15),
          ),
          const SizedBox(height: 3),
          Text(
            meta,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
          ),
          const Spacer(),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              _pill(status, color),
              const SizedBox(width: 5),
              _pill(vacancy.source, sourceColor),
              if (vacancy.matchedProfiles.isNotEmpty) ...[
                const SizedBox(width: 5),
                const Icon(Icons.check_circle, size: 13, color: AppTheme.success),
              ],
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _salary(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.right,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                    height: 1,
                    color: (vacancy.salaryFrom != null || vacancy.salaryTo != null)
                        ? AppTheme.salary
                        : AppTheme.muted,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 24,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.zero,
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                      textStyle: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700),
                    ),
                    onPressed: () => state.applyVacancy(vacancy.id),
                    child: const Text('Отклик'),
                  ),
                ),
              ),
              Expanded(
                child: SizedBox(
                  height: 24,
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      padding: EdgeInsets.zero,
                      minimumSize: Size.zero,
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      visualDensity: VisualDensity.compact,
                      textStyle: const TextStyle(fontSize: 11.5),
                    ),
                    onPressed: () => launchUrl(Uri.parse(vacancy.url), mode: LaunchMode.externalApplication),
                    child: const Text('Открыть'),
                  ),
                ),
              ),
              SizedBox(
                width: 24,
                height: 24,
                child: IconButton(
                  tooltip: 'Игнорировать',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                  visualDensity: VisualDensity.compact,
                  onPressed: () => state.ignoreVacancy(vacancy.id),
                  icon: const Icon(Icons.close, size: 15, color: AppTheme.muted),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _pill(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 10.5, fontWeight: FontWeight.w700),
      ),
    );
  }
}
