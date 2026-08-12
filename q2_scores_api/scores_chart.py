import statistics
import requests
import matplotlib.pyplot as plt

API_URL = "http://localhost:8000/scores"


def fetch_scores():
    """GET the scores. Same reasoning as fetch_books in Q1: timeout so a
    stalled server can't hang the process, raise_for_status so a 404/500
    body never gets treated as data."""
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def validate_scores(raw):
    """
    Split raw records into (clean, rejected).

    A score is valid only if it's present, numeric (int, float, or a string
    that parses as one), and within 0-100. Everything else is dropped and
    reported - not silently averaged away.
    """
    clean = []
    rejected = []

    for record in raw:
        name = record.get("student")
        score = record.get("score")

        if score is None:
            rejected.append((name, score, "missing"))
            continue

        try:
            score = float(score)
        except (TypeError, ValueError):
            rejected.append((name, score, "not numeric"))
            continue

        if not (0 <= score <= 100):
            rejected.append((name, score, "out of 0-100 range"))
            continue

        clean.append({"student": name, "score": score})

    return clean, rejected


def calculate_average(records):
    """Mean of the valid scores only."""
    scores = [r["score"] for r in records]
    return sum(scores) / len(scores)


def plot_scores(records, average):
    """Bar chart of valid scores with the average marked as a dashed line."""
    names = [r["student"] for r in records]
    scores = [r["score"] for r in records]

    fig, ax = plt.subplots()
    ax.bar(names, scores, color="steelblue")
    ax.axhline(y=average, color="red", linestyle="--", label=f"Average: {average:.1f}")
    ax.set_xlabel("Student")
    ax.set_ylabel("Score")
    ax.set_title("Student Test Scores")
    ax.legend()
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()

    fig.savefig("scores_chart.png")
    plt.show()


def main():
    raw = fetch_scores()
    clean, rejected = validate_scores(raw)

    print(f"Fetched {len(raw)} records, {len(clean)} valid, {len(rejected)} rejected")
    for name, score, reason in rejected:
        print(f"  dropped {name!r} (score={score!r}): {reason}")

    average = calculate_average(clean)
    median = statistics.median(r["score"] for r in clean)
    print(f"\naverage: {average:.2f}")
    print(f"median:  {median:.2f}")

    plot_scores(clean, average)


if __name__ == "__main__":
    main()
