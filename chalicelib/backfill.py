"""
    backfill.py
    ~~~~~~


"""
from chalicelib.constants import REPOS
from chalicelib.github import GitHubAPI, get_issues, create_db_session
from chalicelib.models import Issue, PullRequest


ORG = "aws-amplify"


PERIODS = [
    ("2017-01-01", "2017-03-31"),  # q1
    ("2017-04-01", "2017-06-30"),  # q2
    ("2017-07-01", "2017-09-30"),  # q3
    ("2017-10-01", "2017-12-31"),  # q4
    #
    ("2018-01-01", "2018-03-31"),
    ("2018-04-01", "2018-06-30"),
    ("2018-07-01", "2018-09-30"),
    ("2018-10-01", "2018-12-31"),
    #
    ("2019-01-01", "2019-03-31"),  # q1
    ("2019-04-01", "2019-06-30"),  # q2
    ("2019-07-01", "2019-09-30"),  # q3
    ("2019-10-01", "2019-12-31"),  # q4
    #
    ("2020-01-01", "2020-03-31"),
    ("2020-04-01", "2020-06-30"),
    ("2020-07-01", "2020-09-30"),
    ("2020-10-01", "2020-12-31"),
    #
    ("2021-01-01", "2021-03-31"),
    ("2021-04-01", "2021-06-30"),
    ("2021-07-01", "2021-09-30"),
    ("2021-10-01", "2021-12-31"),
]


def backfill_pr_queries():
    """Generate historical GitHub queries for PRs

    Returns:
        list: list of queries
    """
    queries = []
    for repo in REPOS:
        for period in PERIODS:
            queries += [f"repo:{ORG}/{repo} is:pr created:{period[0]}..{period[1]}"]
    return queries


def backfill_issue_queries():
    """Generate historical GitHub queries for issues

    Returns:
        list: list of queries
    """
    queries = []
    for repo in REPOS:
        for period in PERIODS:
            queries += [f"repo:{ORG}/{repo} is:issue created:{period[0]}..{period[1]}"]
    return queries


def backfill_org_prs(db, gh):
    queries = backfill_pr_queries()
    for q in queries:
        prs = get_issues(gh, query=q)
        recs = [PullRequest(**rec) for rec in prs]
        db.add_all(recs)
        db.commit()
    db.close()


def backfill_org_issues(db, gh):
    queries = backfill_issue_queries()
    for q in queries:
        issues = get_issues(gh, query=q)
        recs = [Issue(**rec) for rec in issues]
        db.add_all(recs)
        db.commit()
    db.close()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---
    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)
    # ---

    # backfill_org_prs(db, gh)
    # backfill_org_issues(db, gh)