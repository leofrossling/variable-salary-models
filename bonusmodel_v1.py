import json

from deltek import read_timetables


# return: interntid, rtotalgrundande, rlingrundande, okänt
def daily_result(record: dict, unknown: dict):

    hours = record["numbertransferred"]
    jobnumber = record["jobnumber"]
    jobname = record["description"]
    activitynumber = record["activitynumber"]
    invoicable = record["invoiceable"]

    if invoicable:
        return "billable", hours

    if "9830Internt" == jobnumber:
        return "internal", hours

    if jobnumber not in unknown:
        unknown[jobnumber] = {"description": jobname, "activities": {}}
    if activitynumber not in unknown[jobnumber]["activities"]:
        unknown[jobnumber]["activities"][activitynumber] = {"description": record["entrytext"], "hours": 0}
    unknown[jobnumber]["activities"][activitynumber]["hours"] += hours

    return "unknown", hours


# a, b, c = 0, 0, 0

# unknown_hours = {}
# for record in timetable["panes"]["filter"]["records"]:
#     w, x, y, z = daily_result(record["data"])
#     if record["data"]["jobnumber"] not in unknown_hours:
#         unknown_hours[record["data"]["jobnumber"]] = z
#     else:
#         unknown_hours[record["data"]["jobnumber"]] += z
#     a += w
#     b += x
#     c += y

# print("Non-billable hours: " + str(a))
# print("RTotal hours: " + str(b))
# print("RLinear hours: " + str(c))
# for k in unknown_hours.keys():
#     print("Unknown hours for " + k + ": " + str(unknown_hours[k]))


def calculate_daily_bonus(record: dict):
    return 0, 0, 8


def calculate_years(records: dict[int, dict[int, dict[int, list[dict]]]]):

    base_salary = 10000
    rlon = 93
    rtot = 2000
    rlin = 40

    unknown = {}

    years = {}

    total_hours_per_month = 168  # TODO: Temp Simplification

    for year in records.keys():

        year_rtot = 0
        year_rlon = 0
        year_rlin = 0

        year_bonus_hours = 0

        rtot_bank = 0
        rtot_count = 0

        for month in records[year].keys():

            monthly_bonus_hours = 0
            monthly_non_bonus_hours = 0
            monthly_unknown_hours = 0

            for day in records[year][month].keys():
                for record in records[year][month][day]:
                    time_type, hours = daily_result(record, unknown)

                    match time_type:
                        case "internal":
                            monthly_non_bonus_hours += hours
                        case "unknown":
                            monthly_unknown_hours += hours
                        case "billable":
                            monthly_bonus_hours += hours

            if monthly_bonus_hours >= total_hours_per_month:
                year_rtot += rtot

                rtot_count += 1

                rtot_bank += monthly_bonus_hours - total_hours_per_month
            else:
                if monthly_bonus_hours + rtot_bank >= total_hours_per_month:
                    year_rtot += rtot
                    rtot_count += 1
                    rtot_bank -= total_hours_per_month - monthly_bonus_hours

            year_bonus_hours += monthly_bonus_hours

            year_rlin += rlin * max(monthly_bonus_hours - 130, 0)
            year_rlon += rlon * max(monthly_bonus_hours - 130, 0)

        # Calculate year bonuses
        yearly_hours = total_hours_per_month * 12
        if year_bonus_hours >= yearly_hours - 40:
            if year_bonus_hours >= yearly_hours:
                year_rtot += int(min(1, (year_bonus_hours - yearly_hours) / total_hours_per_month)) * rtot
            else:
                year_rtot += (11 - rtot_count) * rtot

        years[year] = {"rtot": year_rtot, "rlin": year_rlin, "rlon": year_rlon}

        print(f"-- {year} --")
        print(f"  {year_rtot=}")
        print(f"  {year_rlin=}")
        print(f"  {year_rlon=}")
        print(f"  {json.dumps(unknown, indent=2)}")
        print("")


def sort_records(records: list[dict]) -> dict:
    sorted_records = {}
    current_year = 0
    current_month = 0
    for record in records:
        data = record["data"]
        year, month, day = tuple(data["thedate"].split("-"))

        if year not in sorted_records:
            sorted_records[year] = {}
        if month not in sorted_records[year]:
            sorted_records[year][month] = {}
        if day not in sorted_records[year][month]:
            sorted_records[year][month][day] = []

        sorted_records[year][month][day].append(data)

    return sorted_records


def the_main_program():
    records = read_timetables()
    records = sort_records(records)

    calculate_years(records)


if __name__ == "__main__":
    the_main_program()
