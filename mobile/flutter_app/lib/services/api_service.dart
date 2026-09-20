import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiService {
  final http.Client client;
  final String baseUrl;
  String? accessToken;
  String? refreshToken;
  ApiService({http.Client? client, String? baseUrl})
      : client = client ?? http.Client(),
        baseUrl = baseUrl ?? const String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000/api/v1');

  Future<Map<String, dynamic>> request(String path, {Map<String, dynamic>? body, bool retry = true}) async {
    final uri = Uri.parse('$baseUrl$path');
    if (kReleaseMode && uri.scheme != 'https') throw StateError('Release builds require HTTPS');
    final headers = {'Content-Type': 'application/json', if (accessToken != null) 'Authorization': 'Bearer $accessToken'};
    final response = await (body == null ? client.get(uri, headers: headers) : client.post(uri, headers: headers, body: jsonEncode(body))).timeout(const Duration(seconds: 15));
    if (response.statusCode == 401 && retry && refreshToken != null && path != '/auth/refresh') {
      final session = await request('/auth/refresh', body: {'refresh_token': refreshToken}, retry: false);
      accessToken = session['access_token'] as String;
      refreshToken = session['refresh_token'] as String;
      return request(path, body: body, retry: false);
    }
    if (response.statusCode < 200 || response.statusCode >= 300) throw StateError('API request failed (${response.statusCode})');
    final result = jsonDecode(response.body) as Map<String, dynamic>;
    return (result['data'] as Map<String, dynamic>?) ?? {};
  }

  Future<void> login(String email, String password) async {
    accessToken = null; refreshToken = null;
    final session = await request('/auth/login', body: {'email': email, 'password': password}, retry: false);
    accessToken = session['access_token'] as String;
    refreshToken = session['refresh_token'] as String;
  }
  Future<Map<String, dynamic>> dashboard() => request('/dashboard');
  Future<void> logout() async {
    await request('/auth/logout', body: {});
    accessToken = null; refreshToken = null;
  }
  void close() => client.close();
}
