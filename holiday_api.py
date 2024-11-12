import json
import os

import requests


def fetch_holidays_for_year(year) -> dict:
    file_name = f"holidays_{year}.json"
    try:
        with open(file_name, "r") as fp:
            data = json.load(fp)
            return data
    except Exception:
        pass

    if "API_NINJA_KEY" not in os.environ:
        return []
    key = os.environ["API_NINJA_KEY"]

    headers = {
        "X-Api-Key": key,
    }

    url = f"https://api.api-ninjas.com/v1/holidays?country=SWE&year={year}&type=public_holiday"

    print("Fetching holiday dates from API")
    response = requests.get(url, headers=headers, timeout=30)

    if not response.status_code == 200:
        raise Exception(f"Error fetching timetables: {response.reason}")

    holidays = response.json()

    with open(file_name, "w") as fp:
        json.dump(holidays, fp)

    return holidays


def get_easter_holidays(year):
    goodfriday = "error"
    eastermonday = "error"
    holidays = fetch_holidays_for_year(year)

    for holiday in holidays:
        if holiday["name"] == "Good Friday":
            # print("Långfredag är " + holiday['date'])
            goodfriday = holiday["date"]
        if holiday["name"] == "Easter Monday":
            # print("Annandag påsk är " + holiday['date'])
            eastermonday = holiday["date"]

    return goodfriday, eastermonday


def get_ascension_day(year):
    day = "error"
    holidays = fetch_holidays_for_year(year)

    for holiday in holidays:
        if holiday["name"] == "Ascension Day":
            day = holiday["date"]

    return day


def get_midsummers_eve(year):
    day = "error"
    holidays = fetch_holidays_for_year(year)

    for holiday in holidays:
        if holiday["name"] == "Midsummer Day":
            day = holiday["date"]
    if day != "error":
        parts = [int(x) for x in day.split("-")]
        parts[2] -= 1
        day = "-".join([str(x) for x in parts])
    return day


if __name__ == "__main__":
    print(get_midsummers_eve(2025))
