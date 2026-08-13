import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../theme/app_theme.dart';

/// Local brand assets:
/// - companies: square brand icons (favicon / app icon style), not full wordmarks
/// - tech: SVG Simple Icons
class LogoAsset {
  const LogoAsset.png(this.path) : isSvg = false;
  const LogoAsset.svg(this.path) : isSvg = true;

  final String path;
  final bool isSvg;
}

const Map<String, LogoAsset> skillLogos = {
  'Python': LogoAsset.svg('assets/logos/python.svg'),
  'Go': LogoAsset.svg('assets/logos/go.svg'),
  'Java': LogoAsset.svg('assets/logos/java.svg'),
  'JavaScript': LogoAsset.svg('assets/logos/javascript.svg'),
  'TypeScript': LogoAsset.svg('assets/logos/typescript.svg'),
  'Kotlin': LogoAsset.svg('assets/logos/kotlin.svg'),
  'PHP': LogoAsset.svg('assets/logos/php.svg'),
  'C#': LogoAsset.svg('assets/logos/csharp.svg'),
  'C++': LogoAsset.svg('assets/logos/cplusplus.svg'),
  'Rust': LogoAsset.svg('assets/logos/rust.svg'),
  'Ruby': LogoAsset.svg('assets/logos/ruby.svg'),
  'Swift': LogoAsset.svg('assets/logos/swift.svg'),
  'Scala': LogoAsset.svg('assets/logos/scala.svg'),
  'SQL': LogoAsset.svg('assets/logos/sql.svg'),
  'React': LogoAsset.svg('assets/logos/react.svg'),
  'Vue': LogoAsset.svg('assets/logos/vue.svg'),
  'Django': LogoAsset.svg('assets/logos/django.svg'),
  'FastAPI': LogoAsset.svg('assets/logos/fastapi.svg'),
  'Flask': LogoAsset.svg('assets/logos/flask.svg'),
  'Spring': LogoAsset.svg('assets/logos/spring.svg'),
  'Docker': LogoAsset.svg('assets/logos/docker.svg'),
  'Kubernetes': LogoAsset.svg('assets/logos/kubernetes.svg'),
  'AWS': LogoAsset.svg('assets/logos/aws.svg'),
  'PostgreSQL': LogoAsset.svg('assets/logos/postgresql.svg'),
  'Redis': LogoAsset.svg('assets/logos/redis.svg'),
  'Kafka': LogoAsset.svg('assets/logos/kafka.svg'),
  'Node.js': LogoAsset.svg('assets/logos/nodejs.svg'),
  'Flutter': LogoAsset.svg('assets/logos/flutter.svg'),
};

const Map<String, LogoAsset> roleLogos = {
  'Android': LogoAsset.svg('assets/logos/android.svg'),
  'iOS': LogoAsset.svg('assets/logos/apple.svg'),
  'Python': LogoAsset.svg('assets/logos/python.svg'),
  'Java': LogoAsset.svg('assets/logos/java.svg'),
  'Go': LogoAsset.svg('assets/logos/go.svg'),
};

const Map<String, IconData> roleFallbackIcons = {
  'Backend': Icons.dns_rounded,
  'Frontend': Icons.web_asset_rounded,
  'Fullstack': Icons.layers_rounded,
  'Mobile': Icons.smartphone_rounded,
  'QA': Icons.bug_report_rounded,
  'DevOps': Icons.rocket_launch_rounded,
  'SRE': Icons.monitor_heart_rounded,
  'Data': Icons.bar_chart_rounded,
  'ML': Icons.psychology_rounded,
  'Analyst': Icons.analytics_rounded,
  'Architect': Icons.account_tree_rounded,
  'Manager': Icons.groups_rounded,
  'Embedded': Icons.memory_rounded,
  'Security': Icons.security_rounded,
};

const Map<String, IconData> formatFallbackIcons = {
  'remote': Icons.public_rounded,
  'hybrid': Icons.sync_alt_rounded,
  'office': Icons.apartment_rounded,
};

const Map<String, LogoAsset> companyLogos = {
  'Avito': LogoAsset.png('assets/logos/icons/avito.png'),
  'X5 Tech': LogoAsset.png('assets/logos/icons/x5.png'),
  'VK': LogoAsset.png('assets/logos/icons/vk.png'),
  'Raiffeisen': LogoAsset.png('assets/logos/icons/raiffeisen.png'),
  'Ozon': LogoAsset.png('assets/logos/icons/ozon.png'),
  'Яндекс': LogoAsset.png('assets/logos/icons/yandex.png'),
  'Сбер': LogoAsset.png('assets/logos/icons/sber.png'),
  'hh.ru': LogoAsset.png('assets/logos/icons/hh.png'),
  'Wildberries': LogoAsset.png('assets/logos/icons/wildberries.png'),
  'Т-Банк': LogoAsset.png('assets/logos/icons/tbank.png'),
  'Альфа-Банк': LogoAsset.png('assets/logos/icons/alfa-bank.png'),
  'МТС': LogoAsset.png('assets/logos/icons/mts.png'),
  'Контур': LogoAsset.png('assets/logos/icons/kontur.png'),
  'Мегафон': LogoAsset.png('assets/logos/icons/megafon.png'),
  'ВТБ': LogoAsset.png('assets/logos/icons/vtb.png'),
  'Kaspersky': LogoAsset.png('assets/logos/icons/kaspersky.png'),
  'Lamoda': LogoAsset.png('assets/logos/icons/lamoda.png'),
  '2ГИС': LogoAsset.png('assets/logos/icons/2gis.png'),
};

const Map<String, LogoAsset> portalLogos = {
  'habr': LogoAsset.svg('assets/logos/habr.svg'),
  'hh': LogoAsset.png('assets/logos/icons/hh.png'),
};

LogoAsset? skillLogoFor(String name) {
  for (final e in skillLogos.entries) {
    if (e.key.toLowerCase() == name.toLowerCase()) return e.value;
  }
  return null;
}

LogoAsset? companyLogoFor(String label) => companyLogos[label];

/// Logos that are essentially black marks — tint light on dark UI.
const Set<String> _darkMonoLogoPaths = {
  'assets/logos/flask.svg',
  'assets/logos/rust.svg',
  'assets/logos/kafka.svg',
  'assets/logos/apple.svg',
};

class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, required this.asset, this.size = 28});

  final LogoAsset asset;
  final double size;

  @override
  Widget build(BuildContext context) {
    final box = size + 6;
    final tintDark = _darkMonoLogoPaths.contains(asset.path);
    Widget child;
    if (asset.isSvg) {
      child = SvgPicture.asset(
        asset.path,
        width: size,
        height: size,
        fit: BoxFit.contain,
        colorFilter: tintDark
            ? const ColorFilter.mode(Color(0xFFE8DDD6), BlendMode.srcIn)
            : null,
        placeholderBuilder: (_) => Icon(Icons.image_outlined, size: size * 0.7, color: AppTheme.muted),
      );
    } else {
      // cache at 3x for crisp HiDPI
      final px = (size * 3).round();
      child = Image.asset(
        asset.path,
        width: size,
        height: size,
        fit: BoxFit.contain,
        filterQuality: FilterQuality.high,
        isAntiAlias: true,
        cacheWidth: px,
        cacheHeight: px,
        color: tintDark ? const Color(0xFFE8DDD6) : null,
        colorBlendMode: tintDark ? BlendMode.srcIn : null,
        errorBuilder: (_, __, ___) => Icon(Icons.business_rounded, size: size * 0.7, color: AppTheme.muted),
      );
    }

    return SizedBox(
      width: box,
      height: box,
      child: child,
    );
  }
}

class FilterIconChip extends StatelessWidget {
  const FilterIconChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.logo,
    this.icon,
    this.iconColor,
  });

  /// Same height for text-only and icon chips.
  static const double height = 36;
  static const double radius = 8;

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final LogoAsset? logo;
  final IconData? icon;
  final Color? iconColor;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppTheme.accent : AppTheme.textPrimary;
    final ic = iconColor ?? (selected ? AppTheme.accent : AppTheme.textSecondary);
    // Align+widthFactor keeps chip intrinsic-width inside Wrap (otherwise full-row).
    return Align(
      alignment: Alignment.centerLeft,
      widthFactor: 1,
      child: Material(
        color: selected ? AppTheme.accent.withValues(alpha: 0.18) : AppTheme.chip,
        borderRadius: BorderRadius.circular(radius),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(radius),
          child: Container(
            height: height,
            padding: EdgeInsets.fromLTRB(logo != null || icon != null ? 6 : 12, 0, 12, 0),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(radius),
              border: Border.all(color: selected ? AppTheme.accent : AppTheme.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                if (logo != null) ...[
                  BrandLogo(asset: logo!, size: 22),
                  const SizedBox(width: 6),
                ] else if (icon != null) ...[
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: Icon(icon, size: 18, color: ic),
                  ),
                  const SizedBox(width: 6),
                ],
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 12.5,
                    height: 1.1,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
