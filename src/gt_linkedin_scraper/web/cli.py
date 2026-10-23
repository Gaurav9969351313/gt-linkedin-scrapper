"""Bootstrap (or promote) a super admin for the web app.

    python -m gt_linkedin_scraper.web.cli --email you@example.com --name "Your Name"

Prompts for a password. If the email already exists, the account is promoted to an
active super admin and its password is reset.
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.models.app_user import ROLE_SUPER_ADMIN, STATUS_ACTIVE, AppUser
from gt_linkedin_scraper.web.security import MIN_PASSWORD_LENGTH, hash_password, utcnow


def create_super_admin(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args(argv)

    email = args.email.strip().lower()
    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters", file=sys.stderr)
        return 1
    if getpass.getpass("Confirm password: ") != password:
        print("Passwords do not match", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email))
        action = "Promoted" if user else "Created"
        if not user:
            user = AppUser(email=email)
            db.add(user)
        user.name = args.name.strip()
        user.password_hash = hash_password(password)
        user.role = ROLE_SUPER_ADMIN
        user.status = STATUS_ACTIVE
        user.reviewed_at = utcnow()
        db.commit()
    print(f"{action} super admin {email}")
    return 0


def main() -> None:
    raise SystemExit(create_super_admin())


if __name__ == "__main__":
    main()
