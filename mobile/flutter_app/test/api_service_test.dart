import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:flutter_app/services/api_service.dart';

void main() {
  test('failed login cannot create a session', () async {
    final api = ApiService(client: MockClient((_) async => http.Response('{}', 401)));
    await expectLater(api.login('user@example.com', 'wrong'), throwsStateError);
    expect(api.accessToken, isNull);
    api.close();
  });
  test('dashboard uses the real bearer token', () async {
    final api = ApiService(client: MockClient((request) async {
      if (request.url.path.endsWith('/auth/login')) return http.Response('{"data":{"access_token":"test-access","refresh_token":"test-refresh"}}', 200);
      expect(request.headers['Authorization'], 'Bearer test-access');
      return http.Response('{"data":{"total_content":3}}', 200);
    }));
    await api.login('user@example.com', 'example');
    expect((await api.dashboard())['total_content'], 3);
    api.close();
  });
}
