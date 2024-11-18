import json


class timeline_sheet_record:
    def __init__(self):
        pass


class timecode_mapping:

    def __init__(self):
        pass

    def __init__(self, path: str):
        self.load_mapping(path)

    def load_mapping(self, path: str) -> bool:
        self.mappings = {}
        self.path = path
        try:
            with open(self.path, "r") as fp:
                self.mappings = json.load(fp)
                return True
        except Exception as e:
            print(str(e))
            return False

    def save_mapping(self) -> bool:
        try:
            with open(self.path, "w") as fp:
                json.dump(self.mappings, fp)
                return True
        except Exception as e:
            print(str(e))
            return False

    def classify_record(self, record) -> str:

        jobnumber = record["jobnumber"]
        activitynumber = record["activitynumber"]
        taskname = record["taskname"]

        if jobnumber in self.mappings:
            activities = self.mappings[jobnumber]["activities"]
            if activitynumber in activities:
                if taskname in activities[activitynumber]["tasks"]:
                    return activities[activitynumber]["tasks"][taskname]["bonus_type"]
                else:
                    if "bonus_type" in activities[activitynumber]:
                        return activities[activitynumber]["bonus_type"]
            if "any" in activities:
                if taskname in activities["any"]["tasks"]:
                    return activities["any"]["tasks"][taskname]["bonus_type"]
                elif "bonus_type" in activities["any"]:
                    return activities["any"]["bonus_type"]
            if "bonus_type" in self.mappings[jobnumber]:
                return self.mappings[jobnumber]["bonus_type"]

        return "unknown"

    def add_mapping(self, bonus_type: str, jobnumber: str, activitynumber=None, taskname=None):
        if jobnumber not in self.mappings:
            self.mappings[jobnumber] = {"activities": {}}
        if activitynumber is None:
            if "bonus_type" in self.mappings[jobnumber]:
                print("suspected error")
                return
            self.mappings[jobnumber]["bonus_type"] = bonus_type
            return
        if activitynumber not in self.mappings[jobnumber]["activities"]:
            self.mappings[jobnumber]["activities"][activitynumber] = {"tasks": {}}

        if taskname is None:
            if "bonus_type" in self.mappings[jobnumber]["activities"][activitynumber]:
                print("suspected error")
                return
            self.mappings[jobnumber]["activities"][activitynumber]["bonus_type"] = bonus_type
            return

        if taskname not in self.mappings[jobnumber]["activities"][activitynumber]["tasks"]:
            self.mappings[jobnumber]["activities"][activitynumber]["tasks"][taskname] = {"bonus_type": bonus_type}
        return
