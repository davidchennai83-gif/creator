import 'package:flutter/material.dart';
import '../services/api_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final api = ApiService();
  bool busy = false;
  bool signedIn = false;
  String? error;
  Map<String, dynamic>? dashboard;

  @override
  void dispose() {
    email.dispose(); password.dispose(); api.close(); super.dispose();
  }

  Future<void> login() async {
    setState(() { busy = true; error = null; });
    try {
      await api.login(email.text.trim(), password.text);
      final result = await api.dashboard();
      if (!mounted) return;
      setState(() { signedIn = true; dashboard = result; password.clear(); });
    } catch (_) {
      if (mounted) setState(() => error = 'Sign in failed. Check credentials and your server connection.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> logout() async {
    setState(() { busy = true; error = null; });
    try {
      await api.logout();
      if (mounted) setState(() { signedIn = false; dashboard = null; });
    } catch (_) {
      if (mounted) setState(() => error = 'Sign out failed. Please retry.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Creator Platform')),
      body: SingleChildScrollView(padding: const EdgeInsets.all(24), child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (signedIn) ...[
            Text('Signed in', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 20),
            const Text('This app currently supports sign-in only. Use the web dashboard to create videos and manage schedules.'),
            ElevatedButton(onPressed: busy ? null : logout, child: const Text('Sign out')),
          ] else ...[
            const Text('Sign in with an account registered on your web dashboard.'),
            const SizedBox(height: 20),
            TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email')),
            TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
            const SizedBox(height: 20),
            ElevatedButton(onPressed: busy ? null : login, child: const Text('Sign in')),
          ],
          if (busy) const LinearProgressIndicator(),
          if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
        ],
      )),
    );
  }
}
