FORMFIT PHONE CAMERA FIX

1. Replace the old project folder with this folder, or copy these files into your existing formfit_v2 folder:
   - app.py
   - app.js
   - start_formfit_all.bat
   - formfit_local_cert.pem
   - formfit_local_key.pem

2. On the PC, double-click start_formfit_all.bat.

3. On the phone (same Wi-Fi), open:
   https://192.168.1.5:5000

4. Chrome may show a certificate warning because this is a local development certificate. Tap Advanced and continue once. After the HTTPS page loads, Enable camera can request the phone camera.

5. Keep BOTH server windows running. The web server proxies /api/session and /api/analyze_landmarks to the local pose engine, so the phone does not need to reach port 5050 directly.

Important: the certificate is generated for 192.168.1.5. If the PC gets a different LAN IP later, regenerate the certificate for that IP.
