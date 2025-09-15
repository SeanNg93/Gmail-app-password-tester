# Gmail App Password Bulk Tester

A Python utility to **verify Gmail/Google Workspace App Passwords in bulk**.

## Features
- Bulk test Gmail App Passwords from a CSV file
- IMAP + SMTP login verification
- Sequential or parallel execution
- Verbose logs for troubleshooting
- Optional delay between accounts (avoid rate limiting)
- Auto-skip accounts with missing `app_password`

## Requirements
- Python 3.8+
- Internet access (ports 993, 465, 587 open)

## Installation
Clone this repo (no pip install needed, only standard library is used):

```bash
git clone https://github.com/SeanNg93/Gmail-app-password-tester.git
cd Gmail-app-password-tester
```

## CSV Format
Prepare a CSV file with header row:

```
email,app_password
son.nguyen@example.com,xxxx xxxx xxxx xxxx
jenny@example.com,yyyy yyyy yyyy yyyy
empty@example.com,
```
Rows missing `app_password` will be skipped automatically.
Save file as UTF-8 (CSV UTF-8) to avoid encoding issues.

## Usage
Run the script with your CSV:

```bash
python gmail_app_password_tester.py --input mail.csv --sequential --verbose --timeout 20
```

### Options
- `--input FILE` : CSV with email,app_password
- `--out FILE` : Output CSV report (default: app_pw_report.csv)
- `--timeout N` : Timeout per protocol (seconds)
- `--sequential` : Run accounts one by one (recommended)
- `--verbose` : Show detailed log (connect, login steps)
- `--delay-on-success N` : Delay N seconds between accounts if IMAP+SMTP success (e.g., `--delay-on-success 180` for 3 minutes)

### Example
```bash
python gmail_app_password_tester.py --input mail.csv \
  --sequential --verbose --timeout 20 --delay-on-success 180
```

Output:
```
Testing 3 valid account(s) (skipping 1 row(s) missing app_password) with concurrency=1 timeout=20s ...
[son.nguyen@example.com] IMAP=OK; SMTP=OK; 3.21s
[empty@example.com] SKIP (missing app_password)
```

Report file `app_pw_report.csv`:
```
email,imap_ok,imap_error,smtp_ok,smtp_error,elapsed_s
son.nguyen@example.com,OK,,OK,,3.21
empty@example.com,SKIP,missing app_password,SKIP,missing app_password,
```

## Notes
- Only App Passwords are supported (not normal Gmail passwords).
- Use responsibly: testing too many accounts quickly may trigger Google rate limits.
- Do not commit CSV files containing passwords to GitHub.
- Recommended to store CSV in a secure location.
