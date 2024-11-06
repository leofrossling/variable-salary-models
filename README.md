# variable-salary-models
Compare variable salary models with data from Deltek time reporting

## Install and Run

This guide assumes you are using windows.

### Prerequisites
* Python (tested with python 3.12.7)

### Create and activate a python virtual environment:
```
python -m venv .venv
.\.venv\scripts\activate
```

### Generate encoded credentials
Run python in a terminal: ```python```

Replace "USERNAME" and "PASSWORD" with your login details:
```python
import base64

username = "USERNAME"
password = "PASSWORD"

base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
```

Copy the output, create a new file in the repo ".env" and add a text line with DELTEK_CREDENTIALS="CREDENTIALS". Replace CREDENTIALS with the output you copied. E.g. ```DELTEK_CREDENTIALS="VVNFUk5BTUU6UEFTU1dPUkQ="```

#### Run the code

Either import the functions from deltek.py in to your own script or run ```python .\deltek.py```.