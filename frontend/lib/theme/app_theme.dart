import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Muted coral + soft mauve on warm charcoal
  static const bg = Color(0xFF12100F);
  static const surface = Color(0xFF1C1817);
  static const surfaceAlt = Color(0xFF26201E);
  static const border = Color(0xFF3D342F);
  static const textPrimary = Color(0xFFF3EBE6);
  static const textSecondary = Color(0xFFAFA099);
  static const accent = Color(0xFFD9927A);
  static const accentSoft = Color(0xFFB8745F);
  static const accentAlt = Color(0xFFC98FA8);
  static const success = Color(0xFF5CB88A);
  static const warning = Color(0xFFD9927A);
  static const danger = Color(0xFFD97A7A);
  static const muted = Color(0xFF857870);
  static const salary = Color(0xFFC98FA8);
  static const chip = Color(0xFF2A2421);

  static Color sourceColor(String source) => switch (source.toLowerCase()) {
        'habr' => const Color(0xFFD9927A),
        'hirify' => const Color(0xFFC98FA8),
        'talanto' => const Color(0xFFD4A88A),
        'getmatch' => const Color(0xFFBFA0B0),
        'hh' => const Color(0xFFD98A7A),
        'remoteok' => const Color(0xFF7A9FD9),
        'remotive' => const Color(0xFF7AD9B0),
        'himalayas' => const Color(0xFF9B7AD9),
        'jobicy' => const Color(0xFFD9C27A),
        'arbeitnow' => const Color(0xFF7AC5D9),
        'weworkremotely' => const Color(0xFFD97AAB),
        'workingnomads' => const Color(0xFF7AD9C8),
        'greenhouse' => const Color(0xFF8FB87A),
        _ => accent,
      };

  static ThemeData get dark {
    final base = ThemeData.dark(useMaterial3: true);
    final textTheme = GoogleFonts.ibmPlexSansTextTheme(base.textTheme).apply(
      bodyColor: textPrimary,
      displayColor: textPrimary,
    );
    return base.copyWith(
      scaffoldBackgroundColor: bg,
      textTheme: textTheme,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        secondary: accentAlt,
        surface: surface,
        error: danger,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        elevation: 0,
        titleTextStyle: GoogleFonts.ibmPlexSans(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: border),
        ),
      ),
      dividerColor: border,
      navigationRailTheme: const NavigationRailThemeData(
        backgroundColor: surface,
        selectedIconTheme: IconThemeData(color: accent),
        selectedLabelTextStyle: TextStyle(color: accent, fontSize: 12, fontWeight: FontWeight.w600),
        unselectedIconTheme: IconThemeData(color: muted),
        unselectedLabelTextStyle: TextStyle(color: textSecondary, fontSize: 12),
        indicatorColor: Color(0x33D9927A),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceAlt,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: accent),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: const Color(0xFF1A1210),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          side: const BorderSide(color: border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
    );
  }
}
