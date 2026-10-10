FORMFIT LOCAL HTTPS / WIFI FIX
================================

This build fixes the previous problem where HTTPS certificates existed but
app.py still started Flask over plain HTTP. The web server now starts with
the local TLS certificate on port 5000.

CURRENT LAN IP
--------------
The certificate shipped in this build includes the current LAN IP detected
for this package (192.168.1.33). On later Wi-Fi changes, app.py detects the
active private IPv4 and refreshes the server certificate while keeping the
same local CA.

START
-----
Run start_formfit_all.bat from the project folder.

The console prints:
  PC:    https://127.0.0.1:5000
  Phone: https://<current-LAN-IP>:5000
  Trust CA once: https://<current-LAN-IP>:5000/formfit-ca.crt

PHONE TRUST (ONE TIME PER PHONE)
--------------------------------
1. Open the Trust CA URL on the phone.
2. Install/import formfit-local-ca.crt as a CA certificate using the
   phone's certificate/security settings.
3. Re-open the Phone HTTPS URL.

IMPORTANT
---------
- Do NOT delete or replace formfit_users.db. It contains the local user data.
- Do NOT use http://<IP>:5000 anymore. Use https://<IP>:5000.
- If Chrome has an old HTTP tab open, close it and enter the HTTPS URL again.
- The pose API remains local-only on 127.0.0.1:5050; the phone never needs
  to connect directly to port 5050.
