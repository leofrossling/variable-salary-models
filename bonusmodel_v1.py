import calendar as cal
import io
import json
import math
import os
import sys
from getpass import getpass

from consolemenu import ConsoleMenu
from consolemenu.items import CommandItem, ExternalItem, FunctionItem, SubmenuItem
from consolemenu.menu_component import Dimension
from consolemenu.menu_formatter import MenuFormatBuilder

from deltek import UnauthorizedException, read_dailysheetlines
from holiday_api import get_ascension_day, get_easter_holidays, get_midsummers_eve
from timecode_mapping import timecode_mapping

state = {
    "records": None,
    "unknown": None,
    "username": None,
    "report": None,
    "mapping": timecode_mapping("timecode_mapping.json"),
}

bonus_types = ["internal", "bonus", "billable", "VAB", "förtroendeuppdrag", "Föräldraledighet", "unknown"]


class ClearingSubmenuItem(SubmenuItem):

    def action(self):
        self.menu.prologue_text = None
        self.get_submenu().start()


def day_to_string(date):
    match date.weekday():
        case 0:
            return "Monday"
        case 1:
            return "Tuesday"
        case 2:
            return "Wednesday"
        case 3:
            return "Thursday"
        case 4:
            return "Friday"
        case 5:
            return "Saturday"
        case 6:
            return "Sunday"
        case _:
            return "hmm"


def get_monthly_billable_hours_by_year(year: int):
    goodfriday, eastermonday = get_easter_holidays(year)
    ascension_day = get_ascension_day(year)
    calendar = cal.Calendar()
    res = []
    for i in range(12):
        month = i + 1
        count = 0
        for date in calendar.itermonthdates(year, month):
            if date.month != month or date.year != year:
                continue
            if date.weekday() == 5 or date.weekday() == 6:
                continue
            if date.month == 1 and date.day == 1:
                # New years day
                continue
            if date.month == 1 and date.day == 6:
                # Trettondagen
                continue
            if date.isoformat() in [goodfriday, eastermonday]:
                # Påsken
                continue
            if date.month == 5 and date.day == 1:
                # First of May
                continue
            if date.isoformat() == ascension_day:
                # Ascension Day
                continue
            if date.month == 6 and date.day == 6:
                # Nationaldagen
                continue
            if date.month == 12 and date.day in [24, 25, 26, 31]:
                # Jul och nyårsafton
                continue
            count += 1
        if month == 6:
            # Midsommarafton
            count -= 1
        res.append(count * 8)

    return res


# return: interntid, rtotalgrundande, rlingrundande, okänt
def daily_result(record: dict, unknown: dict, mapper: timecode_mapping):

    hours = record["numbertransferred"]
    jobnumber = record["jobnumber"]
    jobname = record["description"]
    activitynumber = record["activitynumber"]
    invoicable = record["invoiceable"]
    internaljob = record["internaljob"]
    taskname = record["taskname"]

    res = {
        "jobnumber": jobnumber,
        "activitynumber": activitynumber,
        "taskname": taskname,
        "hours": hours,
        "type": mapper.classify_record(record),
    }

    if res["type"] == "unknown":
        if jobnumber not in unknown:
            unknown[jobnumber] = {"description": jobname, "activities": {}}
        if activitynumber not in unknown[jobnumber]["activities"]:
            unknown_record = {"description": record["entrytext"], "hours": 0}
            if invoicable:
                unknown_record["suggested_bonus_type"] = "billable"
            unknown[jobnumber]["activities"][activitynumber] = unknown_record
        unknown[jobnumber]["activities"][activitynumber]["hours"] += hours

    return res


def create_record(jobnumber, activitynumber, taskname, hours, bonus_type):
    return {
        "jobnumber": jobnumber,
        "activitynumber": activitynumber,
        "taskname": taskname,
        "hours": hours,
        "bonus_type": bonus_type,
    }


def print_report(report, output_file=sys.stdout):
    for year in report["years"].keys():
        for month in report["years"][year]["months"].keys():
            month_data = report["years"][year]["months"][month]
            print(f"{year}-{month}  -  Hours for month: {month_data['hours']}h", file=output_file)
            print(f"  Hour thresholds: ", file=output_file)
            print(f"    Rtotal: {month_data['hours_adjusted_rtotal']}", file=output_file)
            print(f"    Rlin: {month_data['hours_adjusted_rlin']}", file=output_file)
            print(f"    Rlön: {month_data['hours_adjusted_rlon']}", file=output_file)
            print(f"  Received Rtotal={month_data['Rtotal']}", file=output_file)
            print(f"  Rtotal hour bank={month_data['rtot_bank']:.1f}h", file=output_file)
            print(f"  Received Rlin={month_data['Rlin']:.1f}h", file=output_file)
            print(f"  Received Rlön={month_data['Rlön']:.1f}h", file=output_file)
            print("", file=output_file)

            grouped_month = {}
            for record in month_data["records"]:
                jobnum = record["jobnumber"]
                actnum = record["activitynumber"]
                taskname = record["taskname"]
                if jobnum not in grouped_month:
                    grouped_month[jobnum] = {}
                if actnum not in grouped_month[jobnum]:
                    grouped_month[jobnum][actnum] = {}
                if taskname not in grouped_month[jobnum][actnum]:
                    grouped_month[jobnum][actnum][taskname] = {"hours": 0, "type": record["type"]}
                grouped_month[jobnum][actnum][taskname]["hours"] += record["hours"]
            print("  Monthly time sheet lines with hours combined:", file=output_file)
            for jobnumber in grouped_month.keys():
                for activitynumber in grouped_month[jobnumber].keys():
                    for taskname in grouped_month[jobnumber][activitynumber].keys():
                        hours = grouped_month[jobnumber][activitynumber][taskname]["hours"]
                        bonus_type = grouped_month[jobnumber][activitynumber][taskname]["type"]
                        if hours == 0:
                            continue
                        print(
                            f"    job={jobnumber}, activity={activitynumber}, task={taskname}, {hours=:.1f}, type={bonus_type}",
                            file=output_file,
                        )

        print(f"", file=output_file)
        print(f"  {report['years'][year]['info']['Rtotal']}", file=output_file)


def print_yearly_report(report, output_file=sys.stdout):
    rtot_val = report["info"]["Rtotal"]
    rlin_val = report["info"]["Rlinear"]
    rlon_val = report["info"]["Rlon"]

    for year in report["years"]:
        print(f"-- {year} --", file=output_file)
        rtot_count = report["years"][year]["info"]["Rtotal_payments"]
        rlin_count = report["years"][year]["info"]["Rlinear_hours"]
        rlon_count = report["years"][year]["info"]["Rlon_hours"]
        print(f"  Rtotal payments: {rtot_count}st", file=output_file)
        print(f"  Rlinear hours:   {rlin_count:.1f}h", file=output_file)
        print(f"  Rlön hours:      {rlon_count:.1f}h", file=output_file)
        rtot_hours_lost = report["years"][year]["info"]["Rtotal_hours_lost"]
        if rtot_hours_lost != 0:
            print(f"  Previous Rtotal hours lost: {rtot_hours_lost:.1f}h", file=output_file)
        # if len(unknown.keys()) > 0:
        #     print(f"  {json.dumps(unknown, indent=2)}", file=output_file)
        print("", file=output_file)
        print(f"  Total current: {rtot_count:.1f}*{rtot_val} + {rlin_count:.1f}*{rlin_val}=", file=output_file)
        print(f"                 {rtot_count*rtot_val + rlin_count*rlin_val:.0f} kr", file=output_file)
        print(f"  Total new:     {rlon_count:.1f}*{rlon_val}=", file=output_file)
        print(f"                 {rlon_count*rlon_val:.0f} kr", file=output_file)


def calculate_years(records: dict[int, dict[int, dict[int, list[dict]]]], unknown: dict = {}):
    mapper = state["mapping"]

    rtot_val = 2000
    rlin_val = 40
    if "RTOTAL" in os.environ:
        rtot_val = int(os.environ["RTOTAL"])
    if "RLIN" in os.environ:
        rlin_val = int(os.environ["RLIN"])
    rlon_val = math.ceil(rlin_val + rtot_val / 38)

    years = {}
    report = {"info": {}, "years": {}}

    report["info"]["Rtotal"] = rtot_val
    report["info"]["Rlinear"] = rlin_val
    report["info"]["Rlon"] = rlon_val

    extra_bonus_hours_from_december = 0
    for year in records.keys():
        if year not in report["years"]:
            report["years"][year] = {"info": {}, "months": {}}
        year_bonus_hours = 0
        year_lon_hours = 0
        hours_by_month: list[int] = get_monthly_billable_hours_by_year(int(year))
        rtot_bank = extra_bonus_hours_from_december  # extra hours not compensated are carried into the next year
        rtot_count = 0.0
        rlin_count = 0
        rlon_count = 0
        for month in records[year].keys():
            if month not in report["years"][year]["months"]:
                report["years"][year]["months"][month] = {"records": []}
            rlon_billable = 0
            monthly_billed_hours = 0
            monthly_bonus_hours = 0
            monthly_non_bonus_hours = 0
            monthly_unknown_hours = 0
            rlin_vacation_hours = 0
            rlon_vacation_hours = 0
            vab_equivalent_hours = 0

            last_day_was_billable = False
            for day in records[year][month].keys():
                day_is_billable = "No"
                for record in records[year][month][day]:
                    parsed_record = daily_result(record, unknown, mapper)

                    report["years"][year]["months"][month]["records"].append(parsed_record)
                    match parsed_record["type"]:
                        case "internal":
                            monthly_non_bonus_hours += parsed_record["hours"]
                        case "unknown":
                            monthly_unknown_hours += parsed_record["hours"]
                        case "billable":
                            monthly_billed_hours += parsed_record["hours"]
                            monthly_bonus_hours += parsed_record["hours"]
                            day_is_billable = "Yes"
                        case "vacation":
                            monthly_bonus_hours += parsed_record["hours"]
                            if last_day_was_billable:
                                rlon_vacation_hours += parsed_record["hours"]
                            if month in ["07", "08", "12", "01"]:
                                rlin_vacation_hours += parsed_record["hours"]
                            parsed_record["type"] += " /w bonus"
                            day_is_billable = "Vacay"
                        case "förtroendeuppdrag":
                            if last_day_was_billable:
                                monthly_bonus_hours += parsed_record["hours"]
                                rlon_billable += parsed_record["hours"]
                                parsed_record["type"] += " /w bonus"
                            day_is_billable = "Förtroendeuppdrag"
                        case "VAB" | "Föräldraledighet":
                            vab_equivalent_hours += parsed_record["hours"]
                        case "bonus":
                            monthly_bonus_hours += parsed_record["hours"]

                # This is relevant for how to count vacay or fiduciary duties,
                # as they count the same as "surrounding time".
                # TODO: Inquire with finance on how this is calculated when ending
                #       assignment during vacation.
                if day_is_billable == "No":
                    last_day_was_billable = False
                elif day_is_billable == "Yes":
                    last_day_was_billable = True

            hour_for_month = hours_by_month[int(month) - 1]
            report["years"][year]["months"][month]["hours"] = hour_for_month

            rtotal_required_hours = hour_for_month - vab_equivalent_hours
            report["years"][year]["months"][month]["hours_adjusted_rtotal"] = rtotal_required_hours
            if monthly_bonus_hours >= rtotal_required_hours:
                rtot_increment = 1
                if vab_equivalent_hours > 0:
                    rtot_increment = min(1.0, monthly_bonus_hours / hour_for_month)
                rtot_count += 1
                excess_bonus_hours = monthly_bonus_hours - rtotal_required_hours
                report["years"][year]["months"][month]["Rtotal"] = "True, with %.1fh hours extra" % (excess_bonus_hours)
                rtot_bank += excess_bonus_hours
                extra_bonus_hours_from_december = excess_bonus_hours
            else:
                extra_bonus_hours_from_december = 0
                if monthly_bonus_hours + rtot_bank >= rtotal_required_hours:
                    rtot_count += 1
                    report["years"][year]["months"][month]["Rtotal"] = "True, using %.1fh from hour bank" % (
                        rtotal_required_hours - monthly_bonus_hours
                    )
                    rtot_bank -= rtotal_required_hours - monthly_bonus_hours
                else:
                    report["years"][year]["months"][month]["Rtotal"] = False
            year_bonus_hours += monthly_bonus_hours

            rlin_threshold = 130
            if rlin_vacation_hours > 0:
                rlin_threshold = max(min(130, monthly_billed_hours / hour_for_month * 130), 0)
            report["years"][year]["months"][month]["hours_adjusted_rlin"] = rlin_threshold
            h_lin = max(monthly_billed_hours - rlin_threshold, 0)

            report["years"][year]["months"][month]["hours_adjusted_rlon"] = 130
            h_lon = max(monthly_billed_hours + rlon_vacation_hours + rlon_billable - 130, 0)
            year_lon_hours += monthly_billed_hours
            rlin_count += h_lin
            rlon_count += h_lon
            report["years"][year]["months"][month]["Rlin"] = h_lin
            report["years"][year]["months"][month]["Rlön"] = h_lon
            report["years"][year]["months"][month]["rtot_bank"] = rtot_bank

        # Calculate year bonuses
        yearly_hours = sum(hours_by_month)
        if year_bonus_hours >= yearly_hours - 40:
            if year_bonus_hours >= yearly_hours:
                rtot_count = 12 + min(1, (year_bonus_hours - yearly_hours) / 168)
                report["years"][year]["info"]["Rtotal"] = "More bonus hours than hours in year. Hard at work!"
                extra_bonus_hours_from_december = (
                    0  # extra bonus hours only carry over if not paid out by excess hours previous year
                )
            else:
                if rtot_count < 11:
                    report["years"][year]["info"]["Rtotal"] = (
                        "Within 40 hours of all hours in year, meaning you got %d retroactively" % (11 - rtot_count)
                    )
                else:
                    report["years"][year]["info"][
                        "Rtotal"
                    ] = "Within 40 hours of all hours in year, but already received 11 Rtotal bonuses, so no adjustment made"
                rtot_count = 11
        else:
            report["years"][year]["info"]["Rtotal"] = (
                "You have %d bonus hours, you need %d (yearly hours - 40) to qualify for retroactive RTotal"
                % (year_bonus_hours, (yearly_hours - 40))
            )
        years[year] = {"rtot": rtot_count, "rlin": rlin_count, "rlon": rlon_count}

        report["years"][year]["info"]["Rtotal_payments"] = rtot_count
        report["years"][year]["info"]["Rlinear_hours"] = rlin_count
        report["years"][year]["info"]["Rlon_hours"] = rlon_count

        report["years"][year]["info"]["Rtotal_hours_lost"] = 0
        if year_lon_hours != year_bonus_hours:
            rtot_hours_lost = year_bonus_hours - year_lon_hours
            report["years"][year]["info"]["Rtotal_hours_lost"] = rtot_hours_lost
    return report


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


def display_monthly_report(menu):
    sf = io.StringIO()
    print_report(state["report"], sf)
    menu.prologue_text = sf.getvalue()


def display_yearly_report(menu):
    sf = io.StringIO()
    print_yearly_report(state["report"], sf)
    menu.prologue_text = sf.getvalue()


def record_to_description_text(record):
    return f"Description: {record['description']}\nJob number: {record['jobnumber']}\nActivitynumber: {record['activitynumber']}\nTask: {record['taskname']}\nHours in report: {record['hours']:.1f}\nCurrent time classification: {record['bonus_type']}"


def update_record_bonus_type(menu, record, bonus_type):
    state["mapping"].add_mapping(bonus_type, record["jobnumber"], record["activitynumber"], record["taskname"])
    record["bonus_type"] = bonus_type
    menu.subtitle = record_to_description_text(record)


def clear_prologue_text(menu):
    menu.prologue_text = None


def edit_timesheet_line_single_menu(record):
    line_menu = ConsoleMenu("How do you want to handle this?")
    line_menu.subtitle = record_to_description_text(record)
    for bonus_type in bonus_types:
        fn_item = FunctionItem(
            f"Update classification to {bonus_type}", update_record_bonus_type, args=[line_menu, record, bonus_type]
        )
        line_menu.append_item(fn_item)

    return line_menu


def edit_timesheet_lines_menu():
    unknown_menu = ConsoleMenu("Breakdown of unknown timesheet lines")

    for jobnumber in state["unknown"]:
        for activitynumber in state["unknown"][jobnumber]["activities"]:
            desc = state["unknown"][jobnumber]["activities"][activitynumber]["description"]
            record = create_record(
                jobnumber,
                activitynumber,
                None,
                state["unknown"][jobnumber]["activities"][activitynumber]["hours"],
                "unknown",
            )
            record["description"] = desc
            line_menu = edit_timesheet_line_single_menu(record)

            submenu = ClearingSubmenuItem(f"{jobnumber} - {record['hours']:6.1f}h - {desc}", line_menu, unknown_menu)
            unknown_menu.append_item(submenu)
    unknown_menu.subtitle = "Edit classification for the following unknown timesheet lines"
    return unknown_menu


def update_rlin_rtot():
    while True:
        try:
            rlin_input = int(input("Enter Rlin: "))
            os.environ["RLIN"] = str(rlin_input)
            break
        except Exception as e:
            pass
    while True:
        try:
            rtotal_input = int(input("Enter Rtotal: "))
            os.environ["RTOTAL"] = str(rtotal_input)
            break
        except Exception as e:
            pass
    rlin_val = 40
    rtot_val = 2000
    if "RTOTAL" in os.environ:
        rtot_val = os.environ["RTOTAL"]
    if "RLIN" in os.environ:
        rtlin_val = os.environ["RLIN"]
    update_rvalues_item.text = f"Update Rlin ({rlin_val}) & Rtotal ({rtot_val})"


def login(menu):
    records = None
    username = state["username"]
    try:
        records = read_dailysheetlines()
        username = "[cached data]"
    except Exception:
        print("Enter username: ")
        username = input()
        password = getpass()
        try:
            records = read_dailysheetlines(username=username, password=password)
        except UnauthorizedException as ue:
            menu.prologue_text = "Could not download time sheets due to " + ue.reason
            return
        except Exception as e:
            menu.prologue_text = "Unexpected error: " + str(e)
            return
    state["records"] = sort_records(records)
    state["unknown"] = {}
    state["username"] = username
    state["report"] = calculate_years(state["records"], state["unknown"])
    menu.subtitle = f"Logged in as user {username}. {len(records)} records loaded."
    menu.remove_item(login_item)

    month_report = FunctionItem("Display monthly report", display_monthly_report, args=[menu])
    year_report = FunctionItem("Display yearly report", display_yearly_report, args=[menu])
    timesheet_lines_menu = edit_timesheet_lines_menu()
    timesheet_lines_classification_menu = ClearingSubmenuItem(
        "Inspect timesheet lines classifications", timesheet_lines_menu, main_menu
    )

    menu.append_item(month_report)
    menu.append_item(year_report)
    menu.append_item(timesheet_lines_classification_menu)


formatter = MenuFormatBuilder(max_dimension=Dimension(160, 1000))
main_menu = ConsoleMenu("Main Menu", exit_option_text="Quit", formatter=formatter)
login_item = FunctionItem("Login", login, kwargs={"menu": main_menu})
update_rvalues_item = None


def build_console_menu():
    menu = main_menu
    clear_prologue_text_item = FunctionItem("Clear text", clear_prologue_text, args=[menu])
    rlin_val = 40
    rtot_val = 2000
    if "RTOTAL" in os.environ:
        rtot_val = os.environ["RTOTAL"]
    if "RLIN" in os.environ:
        rtlin_val = os.environ["RLIN"]
    update_rvalues = FunctionItem(f"Update Rlin ({rlin_val}) & Rtotal ({rtot_val})", update_rlin_rtot)
    update_rvalues_item = update_rvalues
    menu.append_item(clear_prologue_text_item)
    menu.append_item(login_item)
    menu.append_item(update_rvalues)
    return menu


def the_main_program():
    menu = build_console_menu()

    menu.show()
    return

    print("")
    print("")
    print("~~~ Welcome to the Salary Calculator ~~~")
    if "VERBOSE" not in os.environ or os.environ["VERBOSE"].lower() != "true":
        print("")
        print(f"  To diplay more information, run with envar VERBOSE=true")
    records = []
    try:
        records = read_dailysheetlines()
    except Exception:
        print("Enter username: ")
        username = input()
        password = getpass()
        try:
            records = read_dailysheetlines(username=username, password=password)
        except UnauthorizedException as ue:
            print("Unable to execute program")
            print("  Could not download time sheets due to: ")
            print(f"   {ue.reason}")
            print("")
            print("exiting...")
            return
        except Exception as e:
            print("Unable to execute program due to unexpected error")
            print("  errorMessage: " + str(e))
            print("")
            print("exiting...")
            return

    records = sort_records(records)

    print("")
    report = calculate_years(records)
    if "VERBOSE" in os.environ and os.environ["VERBOSE"].lower() == "true":
        print("")
        input("Press enter to diplay monthly breakdown")
        print_report(report)


if __name__ == "__main__":
    os.environ["VERBOSE"] = "true"
    the_main_program()
