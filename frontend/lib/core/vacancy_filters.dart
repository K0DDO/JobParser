class VacancyFilters {
  String q;
  List<String> sources;
  List<String> workFormats;
  List<String> experiences;
  List<String> statuses;
  List<String> applicationStatuses;
  int? salaryFrom;
  int? salaryTo;
  String? currency;
  List<String> cities;
  List<String> companies;
  List<String> skills;
  List<String> roles;
  int? maxAgeHours;
  bool? hasSalary;
  List<String> employmentTypes;
  List<int> profileIds;
  String sort;

  VacancyFilters({
    this.q = '',
    List<String>? sources,
    List<String>? workFormats,
    List<String>? experiences,
    List<String>? statuses,
    List<String>? applicationStatuses,
    this.salaryFrom,
    this.salaryTo,
    this.currency,
    List<String>? cities,
    List<String>? companies,
    List<String>? skills,
    List<String>? roles,
    this.maxAgeHours,
    this.hasSalary,
    List<String>? employmentTypes,
    List<int>? profileIds,
    this.sort = 'published_at',
  })  : sources = sources ?? [],
        workFormats = workFormats ?? [],
        experiences = experiences ?? [],
        statuses = statuses ?? [],
        applicationStatuses = applicationStatuses ?? [],
        cities = cities ?? [],
        companies = companies ?? [],
        skills = skills ?? [],
        roles = roles ?? [],
        employmentTypes = employmentTypes ?? [],
        profileIds = profileIds ?? [];

  int get activeCount {
    var n = 0;
    if (q.trim().isNotEmpty) n++;
    n += sources.length;
    n += workFormats.length;
    n += experiences.length;
    n += statuses.length;
    n += applicationStatuses.length;
    if (salaryFrom != null) n++;
    if (salaryTo != null) n++;
    if (currency != null) n++;
    n += cities.length;
    n += companies.length;
    n += skills.length;
    n += roles.length;
    if (maxAgeHours != null) n++;
    if (hasSalary != null) n++;
    n += employmentTypes.length;
    n += profileIds.length;
    if (sort != 'published_at') n++;
    return n;
  }

  static void toggle(List<String> list, String value) {
    final i = list.indexWhere((e) => e.toLowerCase() == value.toLowerCase());
    if (i >= 0) {
      list.removeAt(i);
    } else {
      list.add(value);
    }
  }

  static bool has(List<String> list, String value) =>
      list.any((e) => e.toLowerCase() == value.toLowerCase());

  Map<String, String> toQuery() {
    final query = <String, String>{
      'page': '1',
      'page_size': '50',
      'sort': sort,
    };
    if (q.trim().isNotEmpty) query['q'] = q.trim();
    if (sources.isNotEmpty) query['source'] = sources.join(',');
    if (workFormats.isNotEmpty) query['work_format'] = workFormats.join(',');
    if (experiences.isNotEmpty) query['experience'] = experiences.join(',');
    if (statuses.isNotEmpty) query['status'] = statuses.join(',');
    if (applicationStatuses.isNotEmpty) {
      query['application_status'] = applicationStatuses.join(',');
    }
    if (salaryFrom != null) query['salary_from'] = '$salaryFrom';
    if (salaryTo != null) query['salary_to'] = '$salaryTo';
    if (currency != null) query['currency'] = currency!;
    if (cities.isNotEmpty) query['city'] = cities.join(',');
    if (companies.isNotEmpty) query['company'] = companies.join(',');
    if (skills.isNotEmpty) query['skill'] = skills.join(',');
    if (roles.isNotEmpty) query['role'] = roles.join(',');
    if (maxAgeHours != null) query['max_age_hours'] = '$maxAgeHours';
    if (hasSalary != null) query['has_salary'] = hasSalary! ? 'true' : 'false';
    if (employmentTypes.isNotEmpty) query['employment_type'] = employmentTypes.join(',');
    if (profileIds.isNotEmpty) query['profile_id'] = profileIds.join(',');
    return query;
  }

  void clear() {
    q = '';
    sources.clear();
    workFormats.clear();
    experiences.clear();
    statuses.clear();
    applicationStatuses.clear();
    salaryFrom = null;
    salaryTo = null;
    currency = null;
    cities.clear();
    companies.clear();
    skills.clear();
    roles.clear();
    maxAgeHours = null;
    hasSalary = null;
    employmentTypes.clear();
    profileIds.clear();
    sort = 'published_at';
  }
}
