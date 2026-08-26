import os
import json
import smtplib

from playwright.sync_api import sync_playwright
from email.message import EmailMessage
from datetime import datetime


URL = "https://app.the-trackr.com/uk-tech/summer-internships"

STATE_FILE = "internships_seen.json"

EMAIL_ADDRESS = os.environ["TRACKR_EMAIL"]
EMAIL_APP_PASSWORD = os.environ["TRACKR_EMAIL_PASSWORD"]
EMAIL_TO = os.environ["TRACKR_EMAIL_TO"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465


def get_internships():

    internships = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        print("Opening Trackr...")

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        # Give the application a little extra time
        # to render the table.
        page.wait_for_timeout(5000)

        rows = page.locator("tr")

        print(f"Found {rows.count()} table rows.")

        for i in range(rows.count()):

            row = rows.nth(i)

            cells = row.locator("td")

            if cells.count() < 4:
                continue

            company = cells.nth(1).inner_text().strip()
            programme = cells.nth(2).inner_text().strip()
            opening_date = cells.nth(3).inner_text().strip()

            if not company or not programme:
                continue

            # Ignore internships that have not opened.
            if not opening_date:
                continue

            links = row.locator("a")

            if links.count() > 0:

                link = links.first.get_attribute("href")

                if link:

                    if link.startswith("/"):
                        link = "https://app.the-trackr.com" + link

                else:
                    link = URL

            else:
                link = URL

            key = f"{company} | {programme}"

            internships[key] = {
                "company": company,
                "programme": programme,
                "opening_date": opening_date,
                "link": link
            }

        browser.close()

    return internships


def load_seen():

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    except Exception:
        return {}


def save_seen(internships):

    with open(STATE_FILE, "w") as f:
        json.dump(
            internships,
            f,
            indent=2
        )


def send_email(new_internships):

    msg = EmailMessage()

    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO

    if len(new_internships) == 1:

        internship = new_internships[0]

        msg["Subject"] = (
            f"Internship opened: "
            f"{internship['company']}"
        )

    else:

        msg["Subject"] = (
            f"{len(new_internships)} "
            f"new internships opened"
        )

    lines = [
        "New internship application(s) detected on Trackr:",
        ""
    ]

    for internship in new_internships:

        lines.extend([
            f"Company: {internship['company']}",
            f"Programme: {internship['programme']}",
            f"Opening date: {internship['opening_date']}",
            f"Link: {internship['link']}",
            "",
            "----------------------------",
            ""
        ])

    lines.extend([
        f"Detected at: "
        f"{datetime.now().strftime('%d %b %Y %H:%M:%S')}",
        "",
        URL
    ])

    msg.set_content("\n".join(lines))

    with smtplib.SMTP_SSL(
        SMTP_SERVER,
        SMTP_PORT
    ) as smtp:

        smtp.login(
            EMAIL_ADDRESS,
            EMAIL_APP_PASSWORD
        )

        smtp.send_message(msg)

    print(
        f"Email sent for "
        f"{len(new_internships)} internship(s)."
    )


def check_tracker():

    print("Checking Trackr...")

    current = get_internships()

    print(
        f"Found {len(current)} "
        f"currently open internships."
    )

    seen = load_seen()

    if not seen:

        print("First run. Creating baseline.")

        save_seen(current)

        return

    new_internships = []

    for key, internship in current.items():

        if key not in seen:

            new_internships.append(internship)

    if new_internships:

        print(
            f"Found {len(new_internships)} "
            f"new internship(s)."
        )

        for internship in new_internships:

            print(
                internship["company"],
                "-",
                internship["programme"]
            )

        send_email(new_internships)

    else:

        print("No new internships found.")

    save_seen(current)


if __name__ == "__main__":
    check_tracker()