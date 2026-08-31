import os
import json
import smtplib

from playwright.sync_api import sync_playwright
from email.message import EmailMessage
from datetime import datetime


# --------------------------------------------------
# CONFIG
# --------------------------------------------------

TRACKERS = {
    "Summer Internship": {
        "url": "https://app.the-trackr.com/uk-tech/summer-internships",
        "state_file": "internships_seen.json",
    },
    "Spring Week": {
        "url": "https://app.the-trackr.com/uk-tech/spring-weeks",
        "state_file": "spring_weeks_seen.json",
    },
}


EMAIL_ADDRESS = os.environ["TRACKR_EMAIL"]
EMAIL_APP_PASSWORD = os.environ["TRACKR_EMAIL_PASSWORD"]
EMAIL_TO = os.environ["TRACKR_EMAIL_TO"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465


# --------------------------------------------------
# SCRAPE TRACKR PAGE
# --------------------------------------------------

def get_opportunities(page, opportunity_type, url):

    opportunities = {}

    print(f"\nOpening {opportunity_type} tracker...")

    page.goto(
        url,
        wait_until="networkidle",
        timeout=60000
    )

    # Give the application a little extra time
    # to render the table.
    page.wait_for_timeout(5000)

    rows = page.locator("tr")

    print(
        f"Found {rows.count()} table rows "
        f"on {opportunity_type} page."
    )

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

        # Ignore opportunities that have not opened yet.
        if not opening_date:
            continue

        links = row.locator("a")

        link = url

        if links.count() > 0:

            href = links.first.get_attribute("href")

            if href:

                if href.startswith("/"):
                    link = "https://app.the-trackr.com" + href
                else:
                    link = href

        key = f"{company} | {programme}"

        opportunities[key] = {
            "type": opportunity_type,
            "company": company,
            "programme": programme,
            "opening_date": opening_date,
            "link": link
        }

    return opportunities


# --------------------------------------------------
# LOAD / SAVE STATE
# --------------------------------------------------

def load_seen(state_file):

    if not os.path.exists(state_file):
        return {}

    try:

        with open(state_file, "r") as f:
            return json.load(f)

    except Exception as error:

        print(
            f"Could not read {state_file}: {error}"
        )

        return {}


def save_seen(opportunities, state_file):

    with open(state_file, "w") as f:

        json.dump(
            opportunities,
            f,
            indent=2
        )


# --------------------------------------------------
# EMAIL
# --------------------------------------------------

def send_email(new_opportunities):

    msg = EmailMessage()

    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO

    if len(new_opportunities) == 1:

        opportunity = new_opportunities[0]

        msg["Subject"] = (
            f"{opportunity['type']} opened: "
            f"{opportunity['company']}"
        )

    else:

        spring_count = sum(
            1
            for opportunity in new_opportunities
            if opportunity["type"] == "Spring Week"
        )

        internship_count = sum(
            1
            for opportunity in new_opportunities
            if opportunity["type"] == "Summer Internship"
        )

        subject_parts = []

        if spring_count:
            subject_parts.append(
                f"{spring_count} Spring Week"
            )

        if internship_count:
            subject_parts.append(
                f"{internship_count} internship"
            )

        msg["Subject"] = (
            "New opportunities opened: "
            + ", ".join(subject_parts)
        )

    lines = [
        "New opportunity/opportunities detected on Trackr:",
        ""
    ]

    for opportunity in new_opportunities:

        lines.extend([
            f"TYPE: {opportunity['type']}",
            f"Company: {opportunity['company']}",
            f"Programme: {opportunity['programme']}",
            f"Opening date: {opportunity['opening_date']}",
            f"Link: {opportunity['link']}",
            "",
            "----------------------------",
            ""
        ])

    lines.extend([
        f"Detected at: "
        f"{datetime.now().strftime('%d %b %Y %H:%M:%S')}",
        "",
        "Trackr UK Tech Opportunities Monitor"
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
        f"{len(new_opportunities)} "
        f"new opportunity/opportunities."
    )


# --------------------------------------------------
# CHECK ALL TRACKERS
# --------------------------------------------------

def check_tracker():

    print("=" * 60)
    print("Checking Trackr...")
    print("=" * 60)

    all_new_opportunities = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        for opportunity_type, config in TRACKERS.items():

            url = config["url"]
            state_file = config["state_file"]

            try:

                current = get_opportunities(
                    page,
                    opportunity_type,
                    url
                )

                print(
                    f"Found {len(current)} currently open "
                    f"{opportunity_type} opportunities."
                )

                seen = load_seen(state_file)

                if not seen:

                    print(
                        f"First run for {opportunity_type}. "
                        f"Creating baseline."
                    )

                    save_seen(
                        current,
                        state_file
                    )

                    continue

                new_opportunities = []

                for key, opportunity in current.items():

                    if key not in seen:

                        new_opportunities.append(
                            opportunity
                        )

                if new_opportunities:

                    print(
                        f"Found {len(new_opportunities)} new "
                        f"{opportunity_type} opportunity/opportunities."
                    )

                    for opportunity in new_opportunities:

                        print(
                            opportunity["company"],
                            "-",
                            opportunity["programme"]
                        )

                    all_new_opportunities.extend(
                        new_opportunities
                    )

                else:

                    print(
                        f"No new {opportunity_type} "
                        f"opportunities found."
                    )

                save_seen(
                    current,
                    state_file
                )

            except Exception as error:

                print(
                    f"ERROR checking {opportunity_type}: "
                    f"{error}"
                )

        browser.close()

    # Send ONE email containing everything newly detected
    # across both trackers.
    if all_new_opportunities:

        send_email(
            all_new_opportunities
        )

    else:

        print("\nNo new opportunities detected.")

    print("\nCheck complete.")


# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":
    check_tracker()