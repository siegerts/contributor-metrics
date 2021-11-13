import os

from chalice import Chalice

from github import (
    GitHubAPI,
    reconcile_unmerged_closed_prs,
    update_org_members_daily,
    update_org_prs_closed_daily,
    update_org_prs_daily,
)
from utils import get_parameter
from models import create_db_session

app = Chalice(app_name="contibutor-metrics")


token = None
db_url = None

gh = None
db = None


if "AWS_CHALICE_CLI_MODE" not in os.environ:
    # We're running in Lambda...yay

    token = get_parameter("/contributor-metrics/prod/db_url", True)
    db_url = get_parameter("/contributor-metrics/prod/db_url", True)

    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)


# @app.route('/')
# def index():
#     return {'hello': 'world'}


@app.schedule("rate(1 hour)")
def update_prs(event):
    update_org_prs_daily(db, gh)
    update_org_prs_closed_daily(db, gh)
    reconcile_unmerged_closed_prs(db, gh, "2019-01-01")
    update_org_members_daily(db, gh)
