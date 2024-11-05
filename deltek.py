"""Functions to fetch and print timetable records from Deltek Maconomy."""

import base64
import os

import requests


def read_timetables(encoded_credentials: str = "", username: str = "", password: str = "") -> list[dict]:
    """
    Read user timetables from Deltek Maconomy.

    There are multiple ways to supply credentials to login:
    Option 1:
        Set environment variable DELTEK_CREDENTIALS to a base64 encoded string of username:password.
        Can be generate by running "base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")"
    Option 2:
        Set environment variables DELTEK_USERNAME and DELTEK_PASSWORD in clear text.
    Option 3:
        Pass the base64 encoded credentials as an argument.
    Option 4:
        Pass the username and password as arguments.

    Args:
        encoded_credentials (str, optional): base64 encoded credentials. Defaults to "".
        username (str, optional): Username in clear text. Defaults to "".
        password (str, optional): Password in clear text. Defaults to "".

    Raises:
        Exception: Thrown when no valid authentication was provided.
        Exception: Thrown when the HTTP request fails.

    Returns:
        list[dict]: List of timetable records.
    """

    if not encoded_credentials and os.environ["DELTEK_CREDENTIALS"]:
        encoded_credentials = os.environ["DELTEK_CREDENTIALS"]

    if not encoded_credentials:
        password = password if password else (os.environ["DELTEK_PASSWORD"] if os.environ["DELTEK_PASSWORD"] else "")
        username = username if username else (os.environ["DELTEK_USERNAME"] if os.environ["DELTEK_USERNAME"] else "")

        if username and password:
            credentials = f"{username}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

    if not encoded_credentials or not isinstance(encoded_credentials, str):
        raise Exception("No valid authentication provided...")

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Accept-Language": "en-US",
        "Accept": "application/vnd.deltek.maconomy.containers-v2+json",
    }

    url = "https://me52774-webclient.deltekfirst.com/maconomy-api/containers/me52774/dailytimesheetlines/filter"

    response = requests.get(url, headers=headers, timeout=30)

    if not response.status_code == 200:
        raise Exception(f"Error fetching timetables: {response.reason}")

    timetable = response.json()
    records = timetable["panes"]["filter"]["records"]

    return records


def print_records(records: list[dict]) -> None:
    """Print a list of records in a pretty way.

    Args:
        records (list[dict]): List of timetable records.
    """

    print(" ---- RECORDS ----")

    bonus_tot = 0
    for record in records:
        data = record["data"]
        print(data["thedate"], end=" ")
        if "Internt" in data["jobnumber"]:
            print("(Icke bonusgrundande)")
        else:
            print("")
            bonus_tot += data["numberof"]

        print(f'  Job name: {data["description"]}')
        print(f'  Task: {data["entrytext"]}')
        print(f'  Time: {data["numberof"]} {data["timeregistrationunit"]}')
        print("______________________")

    print("")
    print(f" {bonus_tot} total hours contributing to bonus")


if __name__ == "__main__":
    timetable_records = read_timetables()
    print_records(timetable_records)
