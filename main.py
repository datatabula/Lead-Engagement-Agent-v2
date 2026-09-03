import json
from models import LEAInput
from pipeline import run_pipeline
from writing_generator import print_readable_output

with open("sample_input.json") as f:
    data = json.load(f)

#"is found_contact currently sitting in the file as a real nested JSON object? If it is,
#convert it into a string. if it's not a json obj, leave it as is.
#data.get("found_contact") — this reads the value stored under the
#"found_contact" key in the data dictionary (the one we just loaded from sample_input.json).
#We use .get() instead of data["found_contact"] because .get() returns None if the key doesn't exist at all,
#rather than crashing with a KeyError — a small safety habit for reading dictionary values
if isinstance(data.get("found_contact"), dict):       #this checks whether that value is
                                #actually a Python dictionary (meaning: a nested JSON object,
                                # like {"submitted_lead": "Marukome", ...}) as opposed to something
                                # else, like a plain string or None.
    #json.dumps(...) does the opposite of json.load(...) — instead of turning JSON text
    #into a Python object, it turns a Python object (here, the nested dict) back into JSON text
    data["found_contact"] = json.dumps(data["found_contact"], ensure_ascii=False)

lead = LEAInput(**data)

leav2_output= run_pipeline(lead)

print_readable_output(leav2_output, lead)