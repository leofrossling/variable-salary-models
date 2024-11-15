import json
import os
import math
import calendar as cal
from termcolor import colored
from getpass import getpass

from deltek import read_dailysheetlines, UnauthorizedException
from holiday_api import get_easter_holidays, get_ascension_day, get_midsummers_eve

_rtotal_color = 'yellow'
_rlin_color = 'blue'
_rlon_color = 'green'

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
def daily_result(record: dict, unknown: dict):

    hours = record["numbertransferred"]
    jobnumber = record["jobnumber"]
    jobname = record["description"]
    activitynumber = record["activitynumber"]
    invoicable = record["invoiceable"]
    internaljob = record["internaljob"]
    taskname = record["taskname"]
    desc = record["entrytext"]

    res = {
        'jobnumber':jobnumber,
        'activitynumber':activitynumber,
        'taskname':taskname,
        'hours':hours,
        'type':'',
        "description": desc
    }

    if invoicable:
        res['type'] = "billable"
        return "billable", res

    # Class for bonusgrundande interntid

    if "9830Internt" == jobnumber:
        bonus_type = ""
        match res['taskname']:
            case "181":
                bonus_type = "bonus"
            case "280":
                bonus_type = "förtroendeuppdrag"
            case _:
                bonus_type = "internal"
        res['type'] = bonus_type
        return bonus_type, res 
    
    if "9930Frånvaro" == jobnumber:
        bonus_type = ""
        match res['taskname']:
            case "120":
                bonus_type = "vacation"
            case "130":
                bonus_type = "parental"
            case "140":
                bonus_type = "VAB"
            case _:
                bonus_type = "internal"
        res['type'] = bonus_type
        return bonus_type, res 

    if internaljob and not invoicable:
        bonus_type = "internal"
        res['type'] = bonus_type
        return bonus_type, res 

        
    if jobnumber not in unknown:
        unknown[jobnumber] = {"description": jobname, "activities": {}}
    unknown[jobnumber]["activities"][activitynumber]["hours"] += hours
    if activitynumber not in unknown[jobnumber]["activities"]:
        unknown[jobnumber]["activities"][activitynumber] = {"description": desc, "hours": 0}

    res['type'] = 'unknown'
    return "unknown", res


def print_report(report):
    for year in report.keys():
        for month in report[year].keys():
            if month == "Rtotal" or month == "Rtotal_december":
                continue
            print(f"{year}-{month}  -  Hours for month: {report[year][month]['hours']}h")
            print(f"  Hour thresholds: ")
            print(f"    {colored('Rtotal', _rtotal_color)}: {report[year][month]['hours_adjusted_rtotal']}")
            print(f"    {colored('Rlin', _rlin_color)}: {report[year][month]['hours_adjusted_rlin']}")
            print(f"    {colored('Rlön', _rlon_color)}: {report[year][month]['hours_adjusted_rlon']}")
            if report[year][month]['Rtotal']:
                print(colored("  Received Rtotal", _rtotal_color))
            else:
                print(colored("  Did not receive Rtotal", 'red'))
            print(f"  Rtotal hour bank={report[year][month]['rtot_bank']:.1f}h")
            print(f"  Received Rlin={report[year][month]['Rlin']:.1f}h")
            print(f"  Received Rlön={report[year][month]['Rlön']:.1f}h")
            print("")

            grouped_month = {}
            for record in report[year][month]['records']:
                jobnum = record['jobnumber']
                actnum = record['activitynumber']
                taskname = record['taskname']
                if jobnum not in grouped_month:
                    grouped_month[jobnum] = {}
                if actnum not in grouped_month[jobnum]:
                    grouped_month[jobnum][actnum] = {}
                if taskname not in grouped_month[jobnum][actnum]:
                    grouped_month[jobnum][actnum][taskname] = {
                        'hours':0,
                        'type':record['type'],
                        'description': record['description']
                    }
                grouped_month[jobnum][actnum][taskname]['hours'] += record['hours']
            print("  Monthly time sheet lines with hours combined:")
            for jobnumber in grouped_month.keys():
                for activitynumber in grouped_month[jobnumber].keys():
                    for taskname in grouped_month[jobnumber][activitynumber].keys():
                        hours = grouped_month[jobnumber][activitynumber][taskname]['hours']
                        bonus_type = grouped_month[jobnumber][activitynumber][taskname]['type']
                        desc = grouped_month[jobnumber][activitynumber][taskname]['description']
                        if hours == 0:
                            continue
                        print(f"    {desc} - job={jobnumber}, activity={activitynumber}, task={taskname}, {hours=:.1f}, type={bonus_type}")

        print(f"")
        print(f"  {report[year]['Rtotal']}")
        if 'Rtotal_december' in report[year]:
            print(f"  {report[year]['Rtotal_december']}h carries over from December")

def calculate_years(records: dict[int, dict[int, dict[int, list[dict]]]]):

    rtot_val = 2000
    rlin_val = 40
    if "RTOTAL" in os.environ:
        rtot_val = int(os.environ["RTOTAL"])
    if "RLIN" in os.environ:
        rlin_val = int(os.environ["RLIN"])
    rlon_val = math.ceil(rlin_val + rtot_val / 37.4)

    print("")
    print(f"Numerical values used: Rtotal={rtot_val} kr, Rlinjär={rlin_val} kr, Rlön={rlon_val} kr")
    print("")
    unknown = {}

    years = {}
    report = {}

    extra_bonus_hours_from_december = 0
    last_day_was_billable=False
    for year in records.keys():
        if year not in report:
            report[year] = {}
        year_bonus_hours = 0
        year_lon_hours = 0
        hours_by_month: list[int] = get_monthly_billable_hours_by_year(int(year))
        rtot_bank = extra_bonus_hours_from_december # extra hours not compensated are carried into the next year
        rtot_count = 0.0
        rlin_count = 0
        rlon_count = 0
        for month in records[year].keys():
            if month not in report[year]:
                report[year][month] = {
                    'records':[]
                }
            rlon_billable = 0
            monthly_billed_hours = 0
            monthly_bonus_hours = 0
            monthly_non_bonus_hours = 0
            monthly_unknown_hours = 0
            rlin_vacation_hours = 0
            rlon_vacation_hours = 0
            vab_equivalent_hours = 0

            for day in records[year][month].keys():
                day_is_billable="No"
                for record in records[year][month][day]:
                    time_type, parsed_record = daily_result(record, unknown)
                    report[year][month]['records'].append(parsed_record)
                    match time_type:
                        case "internal":
                            monthly_non_bonus_hours += parsed_record['hours']
                        case "unknown":
                            monthly_unknown_hours += parsed_record['hours']
                        case "billable":
                            monthly_billed_hours += parsed_record['hours']
                            monthly_bonus_hours += parsed_record['hours']
                            day_is_billable="Yes"
                        case "vacation":
                            monthly_bonus_hours += parsed_record['hours']
                            if last_day_was_billable:
                                rlon_vacation_hours += parsed_record['hours']
                            if month in ["07", "08", "12", "01"]:
                                rlin_vacation_hours += parsed_record['hours']
                            parsed_record['type'] += " /w bonus"
                            day_is_billable="Vacay"
                        case "förtroendeuppdrag":
                            if last_day_was_billable:
                                monthly_bonus_hours += parsed_record['hours']
                                rlon_billable += parsed_record['hours']
                                parsed_record['type'] += " /w bonus"
                            day_is_billable="Förtroendeuppdrag"
                        case "VAB":
                            vab_equivalent_hours += parsed_record['hours']
                        case "parental":
                            vab_equivalent_hours += parsed_record['hours']
                        case "bonus":
                            monthly_bonus_hours += parsed_record['hours']
                
                # This is relevant for how to count vacay or fiduciary duties,
                # as they count the same as "surrounding time".
                # TODO: Inquire with finance on how this is calculated when ending
                #       assignment during vacation.
                if day_is_billable == "No":
                    last_day_was_billable=False
                elif day_is_billable == "Yes":
                    last_day_was_billable=True

            hour_for_month = hours_by_month[int(month) - 1]
            report[year][month]['hours'] = hour_for_month

            rtotal_required_hours = hour_for_month - vab_equivalent_hours
            report[year][month]['hours_adjusted_rtotal'] = rtotal_required_hours
            if monthly_bonus_hours >= rtotal_required_hours:
                rtot_increment = 1
                if vab_equivalent_hours > 0:
                    rtot_increment = min(1.0, monthly_bonus_hours / hour_for_month)
                rtot_count += 1 
                excess_bonus_hours = monthly_bonus_hours - rtotal_required_hours
                report[year][month]['Rtotal'] = 'True, with %.1fh hours extra' % (excess_bonus_hours)
                rtot_bank += excess_bonus_hours
                extra_bonus_hours_from_december = excess_bonus_hours
            else:
                extra_bonus_hours_from_december = 0 
                if monthly_bonus_hours + rtot_bank >= rtotal_required_hours:
                    rtot_count += 1
                    report[year][month]['Rtotal'] = 'True, using %.1fh from hour bank' % (rtotal_required_hours - monthly_bonus_hours)
                    rtot_bank -= rtotal_required_hours - monthly_bonus_hours
                else:
                    report[year][month]['Rtotal'] = False
            year_bonus_hours += monthly_bonus_hours

            rlin_threshold = 130
            if rlin_vacation_hours > 0:
                rlin_threshold = max(min(130,monthly_billed_hours / hour_for_month * 130),0) 
            report[year][month]['hours_adjusted_rlin'] = rlin_threshold
            h_lin = max(monthly_billed_hours - rlin_threshold, 0)

            report[year][month]['hours_adjusted_rlon'] = 130
            h_lon = max(monthly_billed_hours + rlon_vacation_hours + rlon_billable - 130, 0)
            year_lon_hours += monthly_billed_hours + rlon_vacation_hours
            rlin_count += h_lin
            rlon_count += h_lon
            report[year][month]['Rlin'] = h_lin
            report[year][month]['Rlön'] = h_lon
            report[year][month]['rtot_bank'] = rtot_bank
            
            
        # Calculate year bonuses
        yearly_hours = sum(hours_by_month)
        if year_bonus_hours >= yearly_hours - 40:
            if year_bonus_hours >= yearly_hours:
                rtot_count = 12 + min(1, (year_bonus_hours - yearly_hours) / 168)
                report[year]['Rtotal'] = "More bonus hours than hours in year. Hard at work!"
                extra_bonus_hours_from_december = 0 # extra bonus hours only carry over if not paid out by excess hours previous year
            else:
                if rtot_count < 11:
                    report[year]['Rtotal'] = "Within 40 hours of all hours in year, meaning you got %d retroactively" % (11 - rtot_count)
                else:
                    report[year]['Rtotal'] = "Within 40 hours of all hours in year, but already received 11 Rtotal bonuses, so no adjustment made"
                rtot_count = 11
        else:
            report[year]['Rtotal'] = "You have %d bonus hours, you need %d (yearly hours - 40) to qualify for retroactive RTotal" % (year_bonus_hours, (yearly_hours - 40))
        years[year] = {"rtot": rtot_count, "rlin": rlin_count, "rlon": rlon_count}
        if extra_bonus_hours_from_december > 0:
            report[year]['Rtotal_december'] = extra_bonus_hours_from_december

        print(f"-- {year} --")
        print(f"  Rtotal payments: {colored(rtot_count, _rtotal_color)}st")
        print(f"  Rlinear hours:   {colored(f'{rlin_count:.1f}', _rlin_color)}h")
        print(f"  Rlön hours:      {colored(f'{rlon_count:.1f}', _rlon_color)}h")
        if year_lon_hours != year_bonus_hours:
            rtot_hours_lost= year_bonus_hours - year_lon_hours
            print(f"  Previous Rtotal hours lost: {colored(f'{rtot_hours_lost:.1f}', 'red')}h")
        if len(unknown.keys()) > 0:
            print(f"  {json.dumps(unknown, indent=2)}")
        print("")
        
        curr_color = 'green'
        new_color = 'red'
        if rtot_count*rtot_val + rlin_count*rlin_val < rlon_count*rlon_val:
            curr_color = 'red'
            new_color = 'green'
            
        print(f"  Total current: {rtot_count:.1f}*{rtot_val} + {rlin_count:.1f}*{rlin_val}=")
        print(f"                 {colored(f'{rtot_count*rtot_val + rlin_count*rlin_val:.0f}', curr_color)} kr")
        print(f"  Total new:     {rlon_count:.1f}*{rlon_val}=")
        print(f"                 {colored(f'{rlon_count*rlon_val:.0f}', new_color)} kr")
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


def the_main_program():
    print("")
    print("")
    print("~~~ Welcome to the Salary Calculator ~~~")
    if "VERBOSE" not in os.environ or os.environ["VERBOSE"].lower() != "true":
        print("")
        print(f"  To diplay more information, run with envar VERBOSE=true")

    print("")
    print("  This programm will is inteded to compare the current traditional salary model")
    print("  with the proposed changes to the salary model.")
    print("  NOTE: Some features are not implemented, such as part-time parental leave or part-time leave.")
    print("")

    records = []
    try:
        records = read_dailysheetlines()
    except Exception:
        print("")
        print("  This program will use your Deltek credentials to download your reported timesheet lines.")
        print("  The credentials are not stored, but the timesheet lines are. They can be deleted after the program is run.")
        print("")
        username = input("Enter Deltek username: ")
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
    if True or "VERBOSE" in os.environ and os.environ["VERBOSE"].lower() == "true":
        print("")
        input("Press enter to diplay monthly breakdown")
        print_report(report)


if __name__ == "__main__":
    the_main_program()
        
