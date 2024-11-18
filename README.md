# variable-salary-models

Compare variable salary models with data from Deltek time reporting.

[Refer to this section for questions on output](#interpret-the-results)

## Install and Run

This guide assumes you are using windows.

### Prerequisites

- Python (tested with python 3.12.7)

### Create and activate a python virtual environment (optional):

```
python -m venv .venv
.\.venv\scripts\activate
```

## Run the program

Run python in a terminal: `python bonusmodel_v1.py`

Environment variable options:
| Envars |
| ------- |
| RTOTAL |
| RLIN |
| VERBOSE |

Example: `RTOTAL=2750 RLIN=50 python bonusmodel_v1.py`

## Interpret the results

### Yearly result

Example output:

```
-- 2024 --
  Rtotal payments: 7.0st                # How many Rtotal payouts for the year
  Rlinear hours:   200.7h               # How many Rlinear qualifying hours
  Rlön hours:      205.9h               # How many Rlön qualifying hours
  Previous Rtotal hours lost: 245.7h    # Number of previously qualifying Rtotal hours
                                        # lost switching models

  Total current: 7.0*2000 + 200.7*40=
                 22027 kr               # Payout old model
  Total new:     205.9*94=
                 19356 kr               # Payout new model
```

Why are the Rlin and Rlön hours different? Here are some of the reasons:

- Vacation is Rlön-qualifying if you are on assignment
- Some timecodes (such as vacation, VAB) could readjust Rlin threshold from 130 hours to something lower

Why have I lost Rtotal hours?

- Previously vacation always provided Rtotal hours
- Some timecodes gave Rtotal before but will not in new model, or not guaranteed at least (up to your superior)

Common pitfalls of current model:

- Rtotal hours only accumulate if you exceed the required number of hours for the month.
- Rtotal is only payed out retroacticely at end of year if you have reported almost the number of hours for the year. Exact threshold for retroactive payhours is `total_hours_for_year - 40`. The retroactive payout of Rtotal will give you a year total of between 11-13 payouts, depending on the number of hours worked.
- The equations for rlin-threshold payout are weird if you work overtime in months with vacation time. For instance, one vacation day in a month with 200 hours worked would result in lower Rlinear payout than without any vacation.

### Monthly result

This is to give insight into how the program has calculated the output. You can also double-check the timecodes and bonus type of each timesheet line.

Example output:

```
2024-04  -  Hours for month: 168h       # The number of working hours in a month differs
  Hour thresholds:
    Rtotal: 168                         # Number used by program to calculate Rtotal
    Rlin: 130                           # Number used by program to calculate Rlin
    Rlön: 130                           # Number used by program to calculate Rlön
  Received Rtotal                       # If Rtotal was payed out for the month
  Rtotal hour bank=36.9h                # How much accumulated Rtotal time you have
  Received Rlin=48.7h                   # Number of hours qualified for Rlin
  Received Rlön=49.7h                   # Number of hours qualified for Rlön

# How each hour was counted by the program
# Note the type, if its incorrect the final calculations might be incorrect
  Monthly time sheet lines with hours combined:
    Konsulttjänst - job=1021490, activity=100, task=100, hours=178.7, type=billable
    Bonusgrundande interntid - job=9830Internt, activity=230, task=181, hours=2.2, type=bonus
    Skyddskommitten - job=9830Internt, activity=230, task=280, hours=1.0, type=förtroendeuppdrag /w bonus
```

## Known limitations

Currently unsupported features are:
Part-time abscence or part-time parental leave. These things adjust Rlinear thresholds in a way that is abscent in the program. But if you did not have a format agreement with your superior to reduce workload to say 80%, then other parental leave should be correct.
