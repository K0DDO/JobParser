import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Dual brand: orange #F5983C + magenta #E55AE7 on warm charcoal
  static const bg = Color(0xFF100D12);
  static const surface = Color(0xFF1A141C);
  static const surfaceAlt = Color(0xFF241C28);
  static const border = Color(0xFF3A2E42);
  static const textPrimary = Color(0xFFF6ECF4);
  static const textSecondary = Color(0xFFB09AAD);
  static const accent = Color(0xFFF5983C);
  static const accentSoft = Color(0xFFC4742A);
  static const accentAlt = Color(0xFFE55AE7);
  static const success = Color(0xFF5ED9A0);
  static const warning = Color(0xFFF5983C);
  static const danger = Color(0xFFFF6B7A);
  static const muted = Color(0xFF7A6A7C);
  static const salary = Color(0xFFE55AE7);
  static const chip = Color(0xFF2A2130);

  static Color sourceColor(String source) => switch (source.toLowerCase()) {
        'habr' => const Color(0xFFF5983C),
        'hirify' => const Color(0xFFE55AE7),
        'talanto' => const Color(0xFFFFB86B),
        'getmatch' => const Color(0xFFD46BE8),
        'hh' => const Color(0xFFFF7A5C),
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
        indicatorColor: Color(0x33F5983C),
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
          foregroundColor: const Color(0xFF1A0F08),
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
