import 'package:intl/intl.dart';

/// API stores UTC; responses are serialized as Europe/Moscow (+03:00).
/// This helper formats those timestamps for the UI.
class MskTime {
  MskTime._();

  static DateTime? parse(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    final dt = DateTime.tryParse(raw);
    if (dt == null) return null;
    // Already offset-aware (MSK from API) — use local wall components for display.
    if (dt.isUtc || raw.endsWith('Z') || _hasOffset(raw)) {
      final msk = dt.toUtc().add(const Duration(hours: 3));
      return DateTime(msk.year, msk.month, msk.day, msk.hour, msk.minute, msk.second);
    }
    // Naive UTC from older payloads
    final asUtc = DateTime.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.millisecond);
    final msk = asUtc.add(const Duration(hours: 3));
    return DateTime(msk.year, msk.month, msk.day, msk.hour, msk.minute, msk.second);
  }

  static bool _hasOffset(String raw) {
    // e.g. 2026-08-12T18:30:00+03:00
    return RegExp(r'[+-]\d{2}:\d{2}$').hasMatch(raw);
  }

  static String format(DateTime? dt, [String pattern = 'HH:mm']) {
    if (dt == null) return '—';
    return DateFormat(pattern).format(dt);
  }

  static String formatApi(String? raw, [String pattern = 'HH:mm']) {
    return format(parse(raw), pattern);
  }

  /// Relative age for vacancy cards, based on published_at (MSK-aware parse).
  static String ageLabel(DateTime? publishedMsk) {
    if (publishedMsk == null) return '';
    final nowMsk = DateTime.now().toUtc().add(const Duration(hours: 3));
    final now = DateTime(nowMsk.year, nowMsk.month, nowMsk.day, nowMsk.hour, nowMsk.minute, nowMsk.second);
    final d = now.difference(publishedMsk);
    if (d.isNegative) return '0ч';
    if (d.inHours < 24) return '${d.inHours}ч';
    return '${d.inDays}д';
  }
}
