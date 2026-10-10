FormFit fix

Replace BOTH files in your web project:
- app.js
- styles.css

The styles.css is copied from the supplied project unchanged.
The app.js keeps the existing pipe rendering and adds safe JSON response handling,
so HTML server errors are shown clearly instead of crashing JSON parsing.

Important: run the Flask web server (app.py), not index.html by double-clicking.
From the project folder:
  python app.py
Then open the URL printed by Flask.
