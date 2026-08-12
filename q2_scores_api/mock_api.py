from fastapi import FastAPI

app = FastAPI()

STUDENTS = [
    {"student": "Aarthi",  "score": 78},
    {"student": "Bharath", "score": 92},
    {"student": "Chitra",  "score": 65},
    {"student": "Deepak",  "score": None},    # absent, no score recorded
    {"student": "Elango",  "score": 88},
    {"student": "Fathima", "score": "74"},    # string, not a number
    {"student": "Ganesh",  "score": 45},
    {"student": "Harini",  "score": 105},     # outside the valid 0-100 range
    {"student": "Ishaan",  "score": 81},
    {"student": "Janani",  "score": 3},       # legitimate but extreme
    {"student": "Karthik", "score": 90},
    {"student": "Lakshmi", "score": 77},
]


@app.get("/scores")
def get_scores():
    return STUDENTS
