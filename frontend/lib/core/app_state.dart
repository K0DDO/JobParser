import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'vacancy_filters.dart';
import '../models/models.dart';

class AppState extends ChangeNotifier {
  AppState(this.api) {
    _startAutoRefresh();
  }

  final ApiClient api;

  DashboardStats? stats;
  List<Vacancy> vacancies = [];
  List<ApplicationItem> applications = [];
  List<SearchProfile> profiles = [];
  List<SourceItem> sources = [];
  List<SystemLog> logs = [];
  AppSettings? settings;

  String? error;
  bool loading = false;
  bool syncing = false;
  final VacancyFilters vacancyFilters = VacancyFilters();
  int vacanciesTotal = 0;
  List<String> filterCities = [];
  List<String> filterCompanies = [];
  List<String> filterSkills = [];

  Timer? _pollTimer;
  String? _knownLastSyncAt;
  bool _pollBusy = false;

  void _startAutoRefresh() {
    _pollTimer?.cancel();
    // Pull dashboard/vacancies when background sync finishes (or every ~45s).
    _pollTimer = Timer.periodic(const Duration(seconds: 45), (_) => _pollBackend());
  }

  Future<void> _pollBackend() async {
    if (_pollBusy || syncing || loading) return;
    _pollBusy = true;
    try {
      final status = await api.get('/sync/status') as Map<String, dynamic>;
      final inProgress = status['sync_in_progress'] as bool? ?? false;
      final lastRaw = status['last_sync_at'] as String?;

      if (inProgress) {
        await loadDashboard();
        return;
      }

      if (lastRaw != null && lastRaw != _knownLastSyncAt) {
        _knownLastSyncAt = lastRaw;
        await Future.wait([
          loadDashboard(),
          loadVacancies(),
          loadFilterOptions(),
          loadSources(),
          loadLogs(),
        ]);
      } else {
        await loadDashboard();
      }
    } catch (_) {
      // Silent poll failures — manual refresh still works.
    } finally {
      _pollBusy = false;
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> bootstrap() async {
    await refreshAll();
    _knownLastSyncAt = (await api.get('/sync/status') as Map<String, dynamic>)['last_sync_at'] as String?;
  }

  Future<void> refreshAll() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      await Future.wait([
        loadDashboard(),
        loadVacancies(),
        loadFilterOptions(),
        loadApplications(),
        loadProfiles(),
        loadSources(),
        loadSettings(),
        loadLogs(),
      ]);
    } catch (e) {
      error = e.toString();
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> loadDashboard() async {
    final data = await api.get('/dashboard');
    stats = DashboardStats.fromJson(data as Map<String, dynamic>);
    notifyListeners();
  }

  Future<void> loadVacancies() async {
    final data = await api.get('/vacancies', query: vacancyFilters.toQuery()) as Map<String, dynamic>;
    vacancies = (data['items'] as List).map((e) => Vacancy.fromJson(e as Map<String, dynamic>)).toList();
    vacanciesTotal = data['total'] as int? ?? vacancies.length;
    notifyListeners();
  }

  Future<void> loadFilterOptions() async {
    final data = await api.get('/vacancies/options') as Map<String, dynamic>;
    filterCities = (data['cities'] as List?)?.map((e) => e.toString()).toList() ?? [];
    filterCompanies = (data['companies'] as List?)?.map((e) => e.toString()).toList() ?? [];
    filterSkills = (data['skills'] as List?)?.map((e) => e.toString()).toList() ?? [];
    notifyListeners();
  }

  Future<void> applyVacancyFilters() async {
    await loadVacancies();
  }

  Future<void> clearVacancyFilters() async {
    vacancyFilters.clear();
    await loadVacancies();
  }

  Future<void> loadApplications() async {
    final data = await api.get('/applications') as List;
    applications = data.map((e) => ApplicationItem.fromJson(e as Map<String, dynamic>)).toList();
    notifyListeners();
  }

  Future<void> loadProfiles() async {
    final data = await api.get('/profiles') as List;
    profiles = data.map((e) => SearchProfile.fromJson(e as Map<String, dynamic>)).toList();
    notifyListeners();
  }

  Future<void> loadSources() async {
    final data = await api.get('/sources') as List;
    sources = data.map((e) => SourceItem.fromJson(e as Map<String, dynamic>)).toList();
    notifyListeners();
  }

  Future<void> loadSettings() async {
    final data = await api.get('/settings') as Map<String, dynamic>;
    settings = AppSettings.fromJson(data);
    notifyListeners();
  }

  Future<void> loadLogs() async {
    final data = await api.get('/logs', query: {'limit': '100'}) as List;
    logs = data.map((e) => SystemLog.fromJson(e as Map<String, dynamic>)).toList();
    notifyListeners();
  }

  Future<void> syncNow() async {
    if (syncing) return;
    syncing = true;
    error = null;
    notifyListeners();
    try {
      await api.post('/sync');
      for (var i = 0; i < 90; i++) {
        await Future.delayed(const Duration(seconds: 2));
        final status = await api.get('/sync/status') as Map<String, dynamic>;
        final inProgress = status['sync_in_progress'] as bool? ?? false;
        if (!inProgress) break;
      }
      await refreshAll();
      _knownLastSyncAt = (await api.get('/sync/status') as Map<String, dynamic>)['last_sync_at'] as String?;
    } catch (e) {
      error = e.toString();
      notifyListeners();
    } finally {
      syncing = false;
      notifyListeners();
    }
  }

  Future<void> enableAutoApply() async {
    await api.post('/automation/enable');
    await loadDashboard();
    await loadSettings();
  }

  Future<void> disableAutoApply() async {
    await api.post('/automation/disable');
    await loadDashboard();
    await loadSettings();
  }

  Future<void> emergencyStop() async {
    await api.post('/automation/emergency-stop');
    await refreshAll();
  }

  Future<void> updateSettings(Map<String, dynamic> body) async {
    await api.patch('/settings', body: body);
    await loadSettings();
    await loadDashboard();
  }

  Future<void> applyVacancy(int id) async {
    await api.post('/vacancies/$id/apply', body: {});
    await loadApplications();
    await loadVacancies();
    await loadDashboard();
  }

  Future<void> ignoreVacancy(int id) async {
    await api.post('/vacancies/$id/ignore');
    await loadVacancies();
    await loadApplications();
  }

  Future<void> createProfile(Map<String, dynamic> body) async {
    await api.post('/profiles', body: body);
    await loadProfiles();
  }

  Future<void> updateProfile(int id, Map<String, dynamic> body) async {
    await api.patch('/profiles/$id', body: body);
    await loadProfiles();
  }

  Future<void> updateSource(int id, Map<String, dynamic> body) async {
    await api.patch('/sources/$id', body: body);
    await loadSources();
  }

  Future<void> updateApplicationStatus(int id, String status) async {
    await api.patch('/applications/$id', body: {'status': status});
    await loadApplications();
    await loadDashboard();
  }
}
