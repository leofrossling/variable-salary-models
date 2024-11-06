import json
import os
import math

from deltek import read_timetables


# return: interntid, rtotalgrundande, rlingrundande, okänt
def daily_result(record: dict, unknown: dict):

    hours = record["numbertransferred"]
    jobnumber = record["jobnumber"]
    jobname = record["description"]
    activitynumber = record["activitynumber"]
    invoicable = record["invoiceable"]
    internaljob = record["internaljob"]
    taskname = record["taskname"]

    res = {
        'jobnumber':jobnumber,
        'activitynumber':activitynumber,
        'taskname':taskname,
        'hours':hours,
        'type':''
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
    if activitynumber not in unknown[jobnumber]["activities"]:
        unknown[jobnumber]["activities"][activitynumber] = {"description": record["entrytext"], "hours": 0}
    unknown[jobnumber]["activities"][activitynumber]["hours"] += hours

    res['type'] = 'unknown'
    return "unknown", res


def print_report(report):
    for year in report.keys():
        for month in report[year].keys():
            if month == "Rtotal":
                continue
            print(f"{year}-{month}")
            print(f"  Received Rtotal={report[year][month]['Rtotal']}")
            print(f"  Rtotal hour bank={report[year][month]['rtot_bank']:.1f}h")
            print(f"  Received Rlin={report[year][month]['Rlin']:.1f}h")
            print(f"  Received Rlon={report[year][month]['Rlön']:.1f}h")
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
                        'type':record['type']
                    }
                grouped_month[jobnum][actnum][taskname]['hours'] += record['hours']
            print("  Monthly time sheet lines with hours combined:")
            for jobnumber in grouped_month.keys():
                for activitynumber in grouped_month[jobnumber].keys():
                    for taskname in grouped_month[jobnumber][activitynumber].keys():
                        hours = grouped_month[jobnumber][activitynumber][taskname]['hours']
                        bonus_type = grouped_month[jobnumber][activitynumber][taskname]['type']
                        if hours == 0:
                            continue
                        print(f"    job={jobnumber}, activity={activitynumber}, task={taskname}, {hours=:.1f}, type={bonus_type}")

        print(f"")
        print(f"  {report[year]['Rtotal']}")

def calculate_years(records: dict[int, dict[int, dict[int, list[dict]]]]):

    rtot_val = int(os.environ["RTOTAL"])
    rlin_val = int(os.environ["RLIN"])
    rlon_val = math.ceil(rlin_val + rtot_val / 38)

    print("")
    print(f"Numerical values used: Rtotal={rtot_val} kr, Rlinjär={rlin_val} kr, Rlön={rlon_val} kr")
    print("")
    unknown = {}

    years = {}
    report = {}

    total_hours_per_month = 168  # TODO: Temp Simplification
    extra_bonus_hours_from_december = 0
    for year in records.keys():
        if year not in report:
            report[year] = {}
        year_bonus_hours = 0

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
            monthly_billable_hours = 0
            monthly_bonus_hours = 0
            monthly_non_bonus_hours = 0
            monthly_unknown_hours = 0
            rlin_vacation_hours = 0
            rlon_vacation_hours = 0
            vab_equivalent_hours = 0

            last_day_was_billable=False
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
                            monthly_billable_hours += parsed_record['hours']
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
                        case "VAB" | "Föräldraledighet":
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

            rtotal_required_hours = total_hours_per_month - vab_equivalent_hours
            if monthly_bonus_hours >= rtotal_required_hours:
                rtot_increment = 1
                if vab_equivalent_hours > 0:
                    rtot_increment = min(1.0, monthly_bonus_hours / total_hours_per_month)
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
                rlin_threshold = max(min(130,monthly_billable_hours / total_hours_per_month * 130),0) 
            h_lin = max(monthly_billable_hours - rlin_threshold, 0)
            h_lon = max(monthly_billable_hours + rlon_vacation_hours + rlon_billable - 130, 0)
            rlin_count += h_lin
            rlon_count += h_lon
            report[year][month]['Rlin'] = h_lin
            report[year][month]['Rlön'] = h_lon
            report[year][month]['rtot_bank'] = rtot_bank
            
            
        # Calculate year bonuses
        yearly_hours = total_hours_per_month * 12
        if year_bonus_hours >= yearly_hours - 40:
            if year_bonus_hours >= yearly_hours:
                rtot_count = 12 + min(1, (year_bonus_hours - yearly_hours) / total_hours_per_month)
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

        print(f"-- {year} --")
        print(f"  {rtot_count=}st")
        print(f"  {rlin_count=:.1f}h")
        print(f"  {rlon_count=:.1f}h")
        print(f"  {json.dumps(unknown, indent=2)}")
        print("")
        print(f"  Total current: {rtot_count:.1f}*{rtot_val} + {rlin_count:.1f}*{rlin_val}=")
        print(f"                 {rtot_count*rtot_val + rlin_count*rlin_val:.0f} kr")
        print(f"  Total new:     {rlon_count:.1f}*{rlon_val}=")
        print(f"                 {rlon_count*rlon_val:.0f} kr")
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
    print("Welcome to the Salary Calculator")
    records = read_timetables()
    print("Sorting time sheet lines")
    records = sort_records(records)

    print("Calculate variable salary per year")
    print("")
    report = calculate_years(records)
    if "VERBOSE" in os.environ and os.environ["VERBOSE"].lower() == "true":
        print_report(report)


if __name__ == "__main__":
    the_main_program()