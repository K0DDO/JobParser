import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_state.dart';
import '../theme/app_theme.dart';
import 'applications_screen.dart';
import 'dashboard_screen.dart';
import 'logs_screen.dart';
import 'profiles_screen.dart';
import 'settings_screen.dart';
import 'sources_screen.dart';
import 'vacancies_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  // Vacancies is the default start page
  int index = 0;

  final pages = const [
    VacanciesScreen(),
    DashboardScreen(),
    ApplicationsScreen(),
    SourcesScreen(),
    ProfilesScreen(),
    LogsScreen(),
    SettingsScreen(),
  ];

  final labels = const [
    'Вакансии',
    'Dashboard',
    'Отклики',
    'Источники',
    'Профили',
    'Логи',
    'Настройки',
  ];

  final icons = const [
    Icons.work_outline,
    Icons.dashboard_outlined,
    Icons.send_outlined,
    Icons.cloud_outlined,
    Icons.rule_folder_outlined,
    Icons.terminal,
    Icons.settings_outlined,
  ];

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.of(context).size.width >= 1000;
    final state = context.watch<AppState>();

    final body = Row(
      children: [
        if (wide)
          NavigationRail(
            backgroundColor: AppTheme.surface,
            selectedIndex: index,
            onDestinationSelected: (i) => setState(() => index = i),
            labelType: NavigationRailLabelType.all,
            leading: Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Column(
                children: [
                  Text(
                    'JobParser',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: AppTheme.accent,
                          letterSpacing: -0.3,
                        ),
                  ),
                  const SizedBox(height: 8),
                  if (state.stats?.globalAutoApply == true)
                    const _Pill(label: 'AUTO ON', color: AppTheme.warning)
                  else
                    const _Pill(label: 'AUTO OFF', color: AppTheme.muted),
                ],
              ),
            ),
            destinations: [
              for (var i = 0; i < labels.length; i++)
                NavigationRailDestination(
                  icon: Icon(icons[i]),
                  label: Text(labels[i]),
                ),
            ],
          ),
        Expanded(child: pages[index]),
      ],
    );

    if (wide) return Scaffold(body: body);

    return Scaffold(
      appBar: AppBar(
        title: const Text('JobParser'),
        actions: [
          PopupMenuButton<int>(
            onSelected: (i) => setState(() => index = i),
            itemBuilder: (_) => [
              for (var i = 0; i < labels.length; i++)
                PopupMenuItem(value: i, child: Text(labels[i])),
            ],
          ),
        ],
      ),
      body: pages[index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: index.clamp(0, 4),
        onDestinationSelected: (i) => setState(() => index = i),
        destinations: [
          for (var i = 0; i < 5; i++)
            NavigationDestination(icon: Icon(icons[i]), label: labels[i]),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.label, required this.color});
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }
}
