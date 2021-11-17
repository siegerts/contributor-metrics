import os
import logging

from chalice import Chalice

from chalicelib.github import (
    GitHubAPI,
    reconcile_unmerged_closed_prs,
    update_org_members_daily,
    update_org_issues_daily,
    update_org_issues_closed_daily,
)
from chalicelib.utils import get_parameter
from chalicelib.models import create_db_session, PullRequest, Issue

app = Chalice(app_name="contributor-metrics")

token = None
db_url = None

gh = None
db = None


if "AWS_CHALICE_CLI_MODE" not in os.environ:
    logging.getLogger().setLevel(logging.INFO)
    # We're running in Lambda...yay
    token = get_parameter("/contributor-metrics/prod/token", True)
    db_url = get_parameter("/contributor-metrics/prod/db_url", True)

    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)


# @app.route('/')
# def index():
#     return {'hello': 'world'}


@app.schedule("rate(30 minutes)")
def every_30_min(event):
    # 5 days back
    # record any new PRs created within
    # the last few days
    # can narrow this intervat in the future
    update_org_issues_daily(db, gh, PullRequest, prs=True)

    # one week back
    # update existing PR status
    # get recently closed PRs and update in the DB
    update_org_issues_closed_daily(db, gh, PullRequest, prs=True)

    # one year back
    # updates the status of a closed PR to reflect
    # the merged/not-merged state
    reconcile_unmerged_closed_prs(db, gh)

    # update any team members
    # store any new team members
    update_org_members_daily(db, gh)

    # ---
    # issues
    update_org_issues_daily(db, gh, Issue, prs=False)
    update_org_issues_closed_daily(db, gh, Issue, prs=False)

    # recently updated issues?


# Run at 5:00am (UTC)/~midnight EST every day.
@app.schedule("cron(0 5 * * ? *)")
def daily(event):
    # updates full historical "closed" state
    # once a day
    # ----
    # updates the status of a closed PR to reflect
    # the merged/not-merged state
    reconcile_unmerged_closed_prs(db, gh, "2019-01-01")
