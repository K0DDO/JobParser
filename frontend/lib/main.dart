import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/app_state.dart';
import 'screens/home_shell.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const JobParserApp());
}

class JobParserApp extends StatelessWidget {
  const JobParserApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider(create: (_) => ApiClient(baseUrl: const String.fromEnvironment(
          'API_BASE_URL',
          defaultValue: 'http://localhost:8000/api/v1',
        ))),
        ChangeNotifierProxyProvider<ApiClient, AppState>(
          create: (context) => AppState(context.read<ApiClient>())..bootstrap(),
          update: (_, api, previous) => previous ?? AppState(api),
        ),
      ],
      child: MaterialApp(
        title: 'JobParser',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark,
        home: const HomeShell(),
      ),
    );
  }
}
