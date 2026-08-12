import 'package:flutter_test/flutter_test.dart';
import 'package:jobparser/main.dart';

void main() {
  testWidgets('App builds', (tester) async {
    await tester.pumpWidget(const JobParserApp());
    await tester.pump();
    expect(find.text('JobParser'), findsWidgets);
  });
}
