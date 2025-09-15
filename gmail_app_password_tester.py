#!/usr/bin/env python3
"""
Gmail App Password bulk tester — v4 (NO-SEND + AUTO-SKIP)
- Verifies IMAP/SMTP login only.
- Automatically SKIP rows where email OR app_password is missing.
- Writes SKIP rows into report with "imap_ok=SKIP, smtp_ok=SKIP".
- Options: --verbose, --sequential, --delay-on-success N (e.g., 180).

CSV columns (UTF-8):
email,app_password
"""

import argparse, csv, time, sys, socket
from typing import Tuple, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import imaplib, smtplib

IMAP_HOST = "imap.gmail.com"
IMAP_PORT_SSL = 993

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT_SSL = 465
SMTP_PORT_STARTTLS = 587

def log(verbose: bool, msg: str):
    if verbose:
        print(msg, flush=True)

def test_imap(email: str, app_password: str, timeout: int, verbose: bool) -> Tuple[bool, str]:
    try:
        log(verbose, f"  [IMAP] Connecting {IMAP_HOST}:{IMAP_PORT_SSL} ...")
        imaplib.Commands['ID'] = ('AUTH','NONAUTH')
        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT_SSL, timeout=timeout) as M:
            log(verbose, "  [IMAP] Connected, logging in ...")
            M.login(email, app_password)
            log(verbose, "  [IMAP] Logged in, NOOP ...")
            M.noop()
            M.logout()
        return True, ""
    except Exception as e:
        return False, str(e)

def test_smtp(email: str, app_password: str, timeout: int, verbose: bool):
    # try SSL 465 first
    try:
        log(verbose, f"  [SMTP] Connecting SSL {SMTP_HOST}:{SMTP_PORT_SSL} ...")
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT_SSL, timeout=timeout)
        log(verbose, "  [SMTP] Connected (SSL). Logging in ...")
        server.login(email, app_password)
        try:
            server.quit()
        except Exception:
            pass
        return True, ""
    except Exception as e_ssl:
        log(verbose, f"  [SMTP] SSL failed: {e_ssl}. Trying STARTTLS on {SMTP_PORT_STARTTLS} ...")
        try:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT_STARTTLS, timeout=timeout)
            server.ehlo()
            server.starttls()
            server.ehlo()
            log(verbose, "  [SMTP] Connected (STARTTLS). Logging in ...")
            server.login(email, app_password)
            try:
                server.quit()
            except Exception:
                pass
            return True, ""
        except Exception as e_tls:
            return False, f"SSL:{e_ssl}; STARTTLS:{e_tls}"

def test_one(email: str, app_password: str, timeout: int, verbose: bool, inter_proto_pause: float = 0.5) -> Dict:
    t0 = time.time()
    imap_ok, imap_err = test_imap(email, app_password, timeout, verbose)
    time.sleep(inter_proto_pause)
    smtp_ok, smtp_err = test_smtp(email, app_password, timeout, verbose)
    dt = round(time.time() - t0, 2)
    return {
        "email": email,
        "imap_ok": imap_ok, "imap_error": imap_err,
        "smtp_ok": smtp_ok, "smtp_error": smtp_err,
        "elapsed_s": dt
    }

def read_accounts(path: str):
    valid: List[Tuple[str, str]] = []
    skipped: List[Dict] = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            email = (r.get("email") or "").strip()
            pw = (r.get("app_password") or "").strip()
            if not email or not pw:
                # prepare a SKIP entry (keep whatever email exists to help identify the row)
                skipped.append({
                    "email": email if email else f"(row {i})",
                    "reason": "missing email" if not email else "missing app_password"
                })
            else:
                valid.append((email, pw))
    return valid, skipped

def write_report(path: str, results: List[Dict], skipped_rows: List[Dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email","imap_ok","imap_error","smtp_ok","smtp_error","elapsed_s"])
        # First write tested results
        for r in results:
            w.writerow([
                r["email"],
                "OK" if r["imap_ok"] else "FAIL",
                r["imap_error"],
                "OK" if r["smtp_ok"] else "FAIL",
                r["smtp_error"],
                r["elapsed_s"]
            ])
        # Append SKIP rows
        for s in skipped_rows:
            w.writerow([
                s["email"],
                "SKIP",
                s["reason"],
                "SKIP",
                s["reason"],
                ""
            ])

def main():
    ap = argparse.ArgumentParser(description="Gmail App Password bulk tester (v4, NO-SEND + AUTO-SKIP)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="app_pw_report.csv")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--verbose", action="store_true", help="Show step-by-step progress")
    ap.add_argument("--sequential", action="store_true", help="Run sequentially (easier to see logs)")
    ap.add_argument("--delay-on-success", type=int, default=0, help="Seconds to wait after each SUCCESS (e.g., 180 for 3 minutes)")
    args = ap.parse_args()

    # Global socket timeout to avoid long hangs (covers DNS/TLS layers too)
    socket.setdefaulttimeout(args.timeout)

    valid_accounts, skipped_rows = read_accounts(args.input)
    print(f"Testing {len(valid_accounts)} valid account(s) "
          f"(skipping {len(skipped_rows)} row(s) missing email/app_password) "
          f"with concurrency={'1' if args.sequential else args.concurrency} timeout={args.timeout}s ...", flush=True)

    # Log skips up front
    for s in skipped_rows:
        print(f"[SKIP] {s['email']}: {s['reason']}", flush=True)

    results: List[Dict] = []

    def post_result(r: Dict):
        results.append(r)
        print(f"[{r['email']}] IMAP={'OK' if r['imap_ok'] else 'FAIL'}; SMTP={'OK' if r['smtp_ok'] else 'FAIL'}; {r['elapsed_s']}s", flush=True)
        if args.delay_on_success and r["imap_ok"] and r["smtp_ok"]:
            print(f"  Sleeping {args.delay_on_success}s before next account (per request)...", flush=True)
            time.sleep(args.delay_on_success)

    if args.sequential or len(valid_accounts) <= 1:
        for email, pw in valid_accounts:
            print(f"--> Testing {email}", flush=True)
            r = test_one(email, pw, args.timeout, args.verbose)
            post_result(r)
    else:
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            futs = {pool.submit(test_one, email, pw, args.timeout, args.verbose): email
                    for (email, pw) in valid_accounts}
            for fut in as_completed(futs):
                r = fut.result()
                post_result(r)

    write_report(args.out, results, skipped_rows)
    print(f"Done. Report written to: {args.out}", flush=True)

if __name__ == "__main__":
    main()
