"""Insert a candidate from the details below.

    python scripts/insert_candidate_from_email.py --resume path/to/cv.pdf
"""
import argparse
from pathlib import Path

from gt_linkedin_scraper.core.sync_database import SessionLocal
from gt_linkedin_scraper.models.candidate import Candidate
from gt_linkedin_scraper.storage.resumes import save_resume
from gt_linkedin_scraper.storage.tags import active_tag_names


CANDIDATE_DETAILS = {
    "name": "Gaurav Talele",
    "number": "+91-9969351313",
    "email": "gauravtalele2025@gmail.com",
    "email_password": "rsaxzwrxcqlzhkbh",
    "tag": "java",
    "subscription": "premium",
    "is_active": True,
    "email_subject": "Job Application For Sr. Java Backend Engineer (Full Stack) | 9 - YoE | NP Serving | Gaurav Talele",
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


def save_resume_file(uploaded_file_path: str, candidate_name: str) -> str | None:
    source = Path(uploaded_file_path) if uploaded_file_path else None
    if not source or not source.exists():
        return None
    return save_resume(source.read_bytes(), source.name, candidate_name)


def main():
    parser = argparse.ArgumentParser(description="Insert candidate from email details")
    parser.add_argument("--resume", required=False, help="Path to resume file")
    parser.add_argument("--tag", default=CANDIDATE_DETAILS["tag"], help="Candidate tag (an active tag name)")
    parser.add_argument("--subscription", default=CANDIDATE_DETAILS["subscription"], help="Subscription")
    parser.add_argument("--email", default=CANDIDATE_DETAILS["email"], help="Candidate email")
    parser.add_argument("--email-password", default=CANDIDATE_DETAILS["email_password"], help="Email password")
    parser.add_argument("--is-active", action="store_true", default=CANDIDATE_DETAILS["is_active"], help="Is active flag")
    args = parser.parse_args()
    with SessionLocal() as db:
        allowed = active_tag_names(db)
    if args.tag not in allowed:
        parser.error(f"--tag must be one of: {', '.join(allowed)}")

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
            email_subject=CANDIDATE_DETAILS["email_subject"],
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
