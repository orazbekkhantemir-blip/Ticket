Python 3.11+; pip install -r requirements.txt
Set environment variables SECRET_KEY (random long string), ADMIN_PASSWORD (strong private password), DB_PATH (persistent disk path).
Run: gunicorn --bind 0.0.0.0:8000 app:app
Deploy to an HTTPS Python host with persistent disk and one shared SQLite database. Customer URL: / ; admin URL: /?admin
Bookings refresh every 3 seconds. SQLite prevents duplicate seats. Payment is manual. Before public use configure HTTPS, secure session cookies, login rate limiting, backups and privacy notice. Do not use ephemeral storage. No hosting account is configured by this package.
