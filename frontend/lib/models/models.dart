import '../core/msk_time.dart';

class DashboardStats {
  DashboardStats({
    required this.totalVacancies,
    required this.newToday,
    required this.matched,
    required this.applications,
    required this.responses,
    required this.interviews,
    required this.offers,
    this.lastSyncAt,
    this.nextSyncAt,
    required this.systemStatus,
    required this.globalAutoApply,
    required this.dryRun,
    required this.syncInProgress,
    required this.queuePending,
  });

  final int totalVacancies;
  final int newToday;
  final int matched;
  final int applications;
  final int responses;
  final int interviews;
  final int offers;
  final DateTime? lastSyncAt;
  final DateTime? nextSyncAt;
  final String systemStatus;
  final bool globalAutoApply;
  final bool dryRun;
  final bool syncInProgress;
  final int queuePending;

  factory DashboardStats.fromJson(Map<String, dynamic> j) => DashboardStats(
        totalVacancies: j['total_vacancies'] as int,
        newToday: j['new_today'] as int,
        matched: j['matched'] as int,
        applications: j['applications'] as int,
        responses: j['responses'] as int,
        interviews: j['interviews'] as int,
        offers: j['offers'] as int,
        lastSyncAt: MskTime.parse(j['last_sync_at'] as String?),
        nextSyncAt: MskTime.parse(j['next_sync_at'] as String?),
        systemStatus: j['system_status'] as String? ?? 'ok',
        globalAutoApply: j['global_auto_apply'] as bool? ?? false,
        dryRun: j['dry_run'] as bool? ?? true,
        syncInProgress: j['sync_in_progress'] as bool? ?? false,
        queuePending: j['queue_pending'] as int? ?? 0,
      );
}

class Vacancy {
  Vacancy({
    required this.id,
    required this.source,
    required this.title,
    this.company,
    this.description,
    this.salaryFrom,
    this.salaryTo,
    this.currency,
    this.originalCurrency,
    this.city,
    required this.remote,
    required this.workFormat,
    required this.experience,
    this.publishedAt,
    this.skills,
    required this.status,
    required this.url,
    this.matchedProfiles = const [],
    this.applicationStatus,
  });

  final int id;
  final String source;
  final String title;
  final String? company;
  final String? description;
  final int? salaryFrom;
  final int? salaryTo;
  final String? currency;
  final String? originalCurrency;
  final String? city;
  final bool remote;
  final String workFormat;
  final String experience;
  final DateTime? publishedAt;
  final List<String>? skills;
  final String status;
  final String url;
  final List<String> matchedProfiles;
  final String? applicationStatus;

  factory Vacancy.fromJson(Map<String, dynamic> j) => Vacancy(
        id: j['id'] as int,
        source: j['source'] as String,
        title: j['title'] as String,
        company: j['company'] as String?,
        description: j['description'] as String?,
        salaryFrom: j['salary_from'] as int?,
        salaryTo: j['salary_to'] as int?,
        currency: j['currency'] as String?,
        originalCurrency: j['original_currency'] as String?,
        city: j['city'] as String?,
        remote: j['remote'] as bool? ?? false,
        workFormat: j['work_format'] as String? ?? 'unknown',
        experience: j['experience'] as String? ?? 'unknown',
        publishedAt: MskTime.parse(j['published_at'] as String?),
        skills: (j['skills'] as List?)?.map((e) => e.toString()).toList(),
        status: j['status'] as String? ?? 'new',
        url: j['url'] as String,
        matchedProfiles: (j['matched_profiles'] as List?)?.map((e) => e.toString()).toList() ?? [],
        applicationStatus: j['application_status'] as String?,
      );
}

class ApplicationItem {
  ApplicationItem({
    required this.id,
    required this.vacancyId,
    required this.status,
    this.vacancyTitle,
    this.vacancyCompany,
    this.vacancySource,
    this.vacancyUrl,
    this.profileName,
    this.appliedAt,
    this.isDryRun = false,
    this.isAuto = false,
  });

  final int id;
  final int vacancyId;
  final String status;
  final String? vacancyTitle;
  final String? vacancyCompany;
  final String? vacancySource;
  final String? vacancyUrl;
  final String? profileName;
  final DateTime? appliedAt;
  final bool isDryRun;
  final bool isAuto;

  factory ApplicationItem.fromJson(Map<String, dynamic> j) => ApplicationItem(
        id: j['id'] as int,
        vacancyId: j['vacancy_id'] as int,
        status: j['status'] as String,
        vacancyTitle: j['vacancy_title'] as String?,
        vacancyCompany: j['vacancy_company'] as String?,
        vacancySource: j['vacancy_source'] as String?,
        vacancyUrl: j['vacancy_url'] as String?,
        profileName: j['profile_name'] as String?,
        appliedAt: MskTime.parse(j['applied_at'] as String?),
        isDryRun: j['is_dry_run'] as bool? ?? false,
        isAuto: j['is_auto'] as bool? ?? false,
      );
}

class SearchProfile {
  SearchProfile({
    required this.id,
    required this.name,
    required this.isActive,
    this.includeSkills,
    this.roles,
    this.salaryFrom,
    this.autoApplyEnabled = false,
    this.dailyApplyLimit = 30,
    this.sources,
  });

  final int id;
  final String name;
  final bool isActive;
  final List<String>? includeSkills;
  final List<String>? roles;
  final int? salaryFrom;
  final bool autoApplyEnabled;
  final int dailyApplyLimit;
  final List<String>? sources;

  factory SearchProfile.fromJson(Map<String, dynamic> j) => SearchProfile(
        id: j['id'] as int,
        name: j['name'] as String,
        isActive: j['is_active'] as bool? ?? true,
        includeSkills: (j['include_skills'] as List?)?.map((e) => e.toString()).toList(),
        roles: (j['roles'] as List?)?.map((e) => e.toString()).toList(),
        salaryFrom: j['salary_from'] as int?,
        autoApplyEnabled: j['auto_apply_enabled'] as bool? ?? false,
        dailyApplyLimit: j['daily_apply_limit'] as int? ?? 30,
        sources: (j['sources'] as List?)?.map((e) => e.toString()).toList(),
      );
}

class SourceItem {
  SourceItem({
    required this.id,
    required this.name,
    required this.displayName,
    required this.parsingEnabled,
    required this.autoApplyEnabled,
    required this.autoApplySupported,
    required this.status,
    this.lastSyncAt,
    this.lastError,
    required this.foundToday,
    this.connected = false,
  });

  final int id;
  final String name;
  final String displayName;
  final bool parsingEnabled;
  final bool autoApplyEnabled;
  final bool autoApplySupported;
  final String status;
  final DateTime? lastSyncAt;
  final String? lastError;
  final int foundToday;
  final bool connected;

  factory SourceItem.fromJson(Map<String, dynamic> j) => SourceItem(
        id: j['id'] as int,
        name: j['name'] as String,
        displayName: j['display_name'] as String,
        parsingEnabled: j['parsing_enabled'] as bool? ?? false,
        autoApplyEnabled: j['auto_apply_enabled'] as bool? ?? false,
        autoApplySupported: j['auto_apply_supported'] as bool? ?? false,
        status: j['status'] as String? ?? 'ready',
        lastSyncAt: MskTime.parse(j['last_sync_at'] as String?),
        lastError: j['last_error'] as String?,
        foundToday: j['found_today'] as int? ?? 0,
        connected: j['connected'] as bool? ?? false,
      );
}

class AppSettings {
  AppSettings({
    required this.syncIntervalMinutes,
    required this.timezone,
    required this.globalAutoApply,
    required this.dryRun,
    required this.globalDailyLimit,
    this.workingHoursStart,
    this.workingHoursEnd,
  });

  final int syncIntervalMinutes;
  final String timezone;
  final bool globalAutoApply;
  final bool dryRun;
  final int globalDailyLimit;
  final String? workingHoursStart;
  final String? workingHoursEnd;

  factory AppSettings.fromJson(Map<String, dynamic> j) => AppSettings(
        syncIntervalMinutes: j['sync_interval_minutes'] as int? ?? 60,
        timezone: j['timezone'] as String? ?? 'Europe/Moscow',
        globalAutoApply: j['global_auto_apply'] as bool? ?? false,
        dryRun: j['dry_run'] as bool? ?? true,
        globalDailyLimit: j['global_daily_limit'] as int? ?? 50,
        workingHoursStart: j['working_hours_start'] as String?,
        workingHoursEnd: j['working_hours_end'] as String?,
      );
}

class SystemLog {
  SystemLog({
    required this.id,
    required this.level,
    required this.category,
    required this.message,
    required this.createdAt,
  });

  final int id;
  final String level;
  final String category;
  final String message;
  final DateTime createdAt;

  factory SystemLog.fromJson(Map<String, dynamic> j) => SystemLog(
        id: j['id'] as int,
        level: j['level'] as String,
        category: j['category'] as String,
        message: j['message'] as String,
        createdAt: MskTime.parse(j['created_at'] as String?) ?? DateTime.now(),
      );
}
