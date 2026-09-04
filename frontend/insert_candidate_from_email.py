import argparse
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gt_linkedin_scraper.models.candidate import Candidate

ALLOWED_TAGS = ["devops", "java", "qa", "freshers", "data_engineer"]

CANDIDATE_DETAILS = {
    "name": "Gaurav Talele",
    "number": "+91-9969351313",
    "email": "gauravtalele2025@gmail.com",
    "email_password": "rsaxzwrxcqlzhkbh",  # Not provided in email
    "tag": "java",
    "subscription": "premium",  # Default subscription
    "is_active": True,
    "email_body": """
    <html>
    <body style=" font-family: Arial, Helvetica, sans-serif; font-size: 22px">
        <h4>Dear Hiring Manager,</h4>
        <h5>I hope you are doing well. <h5>
                <p style="font-weight: normal; line-height: 24px">
                    I am writing to express my strong interest in being the next Sr. Full Stack Developer at your
                    organisation. As an ambitious professional with almost <b>8.10 (almost 9) years of experience</b> in <b>Java, Spring
                        Boot, Angular, Apache Camel, Apache Kafka, Microservices, Axon, Oracle, Jasper Reports, Git, Docker,
                        Docker Compose, CICD, AWS</b>. <br>
                    I believe that I would make an excellent addition to your team. I am currently working as a Senior Java
                    Full Stack Engineer with Bank Of New York Mellon.<br>
                    I have attached my CV hoping that you will consider me for the place in your organisation, should you
                    need more details or references I can supply those at your convenience. Otherwise <b>I would like to
                        have an interview</b> and talk more about being a new employee for your esteemed
                    Organisation.<br><br>
                <table style="font-weight: normal; line-height: 24px;" border=1>
                    <tr>
                        <td style="font-weight: bold;">First Name</td>
                        <td>Gaurav</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Middle Name</td>
                        <td>Yashwant</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Last Name</td>
                        <td>Talele</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Date Of Birth</td>
                        <td>11/02/1994</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">ReLocation Preferences</td>
                        <td> UAE / Dubai / Abu Dhabi / Singapore </td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Notice Period</td>
                        <td>45 Days</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Availability</td>
                        <td>45 Days</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Nationality</td>
                        <td>Indian</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Current City</td>
                        <td>Mumbai, India</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Open For</td>
                        <td>Full Time / Contract / Remote / Hybrid</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Total Relevant YoE</td>
                        <td>8.5 Years</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">PAN Number</td>
                        <td>AUDPT4503C</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Reason for Job Change</td>
                        <td>Looking For better opputunity</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Heighest Qualification</td>
                        <td>Bachelor Of Engineering + PGDAC</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Current Company</td>
                        <td>Bank Of New York Mellon (BNY)</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Experience</td>
                        <td>
                            <table style="font-weight: normal; line-height: 24px;" border=1>
                                <tr>
                                    <td style="font-weight: bold;">Java, Spring Boot</td>
                                    <td>8.5 Years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Angular</td>
                                    <td>5 Years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Microservices</td>
                                    <td>4 Years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Apach Camel</td>
                                    <td>4 years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Apache Kafka, IBM MQ</td>
                                    <td>4 years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Oracle, MongoDB, Redis</td>
                                    <td>5 years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">Docker, Kubernetes</td>
                                    <td>5 years</td>
                                </tr>
                                <tr>
                                    <td style="font-weight: bold;">AWS</td>
                                    <td>4 years</td>
                                </tr>
                                
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">Linked In Profile</td>
                        <td>https://www.linkedin.com/in/gaurav9969351313/</td>
                    </tr>
                   
                    <tr>
                        <td style="font-weight: bold;">Alternate Email ID</td>
                        <td>epostgauravtalele@gmail.com</td>
                    </tr>
                </table>
                <br>
                <br>
                Thank you for your time and consideration. .. :)
                </p>
                <br>
                <p style="line-height: 24px">With Best Regards,<br></p>
                <p style="line-height: 22px; font-weight: normal;">
                    Mr. Gaurav Talele <br>
                    <b>Sr. Java Backend Engineer (Full Stack SDE-2)</b><br>
                    [M]: gauravtalele2025@gmail.com<br>
                    [H]: +91-9969351313
                    <br>
                </p>
    </body>
    </html>
    """,
}


def slugify_name(name: str) -> str:
    value = name.lower()
    value = "".join(ch if ch.isalnum() else "_" for ch in value)
    while "__" in value:
        value = value.replace("__", "_")
    value = value.strip("_")
    return value or "candidate"


def save_resume_file(uploaded_file_path: str, candidate_name: str) -> str | None:
    if not uploaded_file_path or not Path(uploaded_file_path).exists():
        return None
    folder_name = slugify_name(candidate_name)
    upload_dir = Path("ResumeUploads") / folder_name
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / Path(uploaded_file_path).name
    file_path.write_bytes(Path(uploaded_file_path).read_bytes())
    return os.path.relpath(file_path, start="ResumeUploads")


def main():
    load_dotenv()
    database_url = os.environ.get("DATABASE_URL_SYNC", "postgresql+psycopg2://scraper:scraper_pass@localhost:5432/scraper_db")
    engine = create_engine(database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    parser = argparse.ArgumentParser(description="Insert candidate from email details")
    parser.add_argument("--resume", required=False, help="Path to resume file")
    parser.add_argument("--tag", default=CANDIDATE_DETAILS["tag"], choices=ALLOWED_TAGS, help="Candidate tag")
    parser.add_argument("--subscription", default=CANDIDATE_DETAILS["subscription"], help="Subscription")
    parser.add_argument("--email", default=CANDIDATE_DETAILS["email"], help="Candidate email")
    parser.add_argument("--email-password", default=CANDIDATE_DETAILS["email_password"], help="Email password")
    parser.add_argument("--is-active", action="store_true", default=CANDIDATE_DETAILS["is_active"], help="Is active flag")
    args = parser.parse_args()

    resume_path = None
    if args.resume:
        resume_path = save_resume_file(args.resume, CANDIDATE_DETAILS["name"])

    db = SessionLocal()
    try:
        candidate = Candidate(
            name=CANDIDATE_DETAILS["name"],
            number=CANDIDATE_DETAILS["number"],
            subscription=args.subscription,
            is_active=args.is_active,
            email=args.email,
            email_password=args.email_password,
            tag=args.tag,
            resume=resume_path,
            email_body=CANDIDATE_DETAILS["email_body"],
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        print(f"Candidate inserted with id={candidate.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
