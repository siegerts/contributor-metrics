import time
from datetime import date, datetime, timedelta

import requests


try:
    from chalicelib.models import Issue, Member, PullRequest
except ModuleNotFoundError:
    from models import Issue, Member, PullRequest

# from sqlalchemy.exc import IntegrityError, ProgrammingError

# Check reaction count

REPOS = [
    "amplify-cli",
    "amplify-js",
    "amplify-ui",
    "amplify-console",
    "amplify-codegen",
    "amplify-adminui",
    "amplify-flutter",
    "amplify-ios",
    "amplify-android",
    "docs",
]

PERIODS = [
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

ISSUE_PERIODS = [
    ("2017-01-01", "2017-03-31"),  # q1
    ("2017-04-01", "2017-06-30"),  # q2
    ("2017-07-01", "2017-09-30"),  # q3
    ("2017-10-01", "2017-12-31"),  # q4
    #
    ("2018-01-01", "2018-03-31"),
    ("2018-04-01", "2018-06-30"),
    ("2018-07-01", "2018-09-30"),
    ("2018-10-01", "2018-12-31"),
] + PERIODS


class GitHubAPIException(Exception):
    """Invalid API Server Responses"""

    def __init__(self, code, resp):
        self.code = code
        self.resp = resp

    def __str__(self):
        return f"Server Response ({self.code}): {self.resp}"


class GitHubAPI:
    def __init__(self, gh_api="https://api.github.com", token=None):
        self.gh_api = gh_api
        self._token = token

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, token):
        if not token:
            raise Exception("token cannot be empty")
        self._token = token

    def get(self, url, media_type="vnd.github.v3+json", **params):
        """Wrapper GET method around the GitHub REST API

        Args:
            url (str): GitHub REST API endpoint
            media_type (str, optional): Defaults to "vnd.github.v3+json".

        Raises:
            GitHubAPIException: [description]

        Returns:
            dict: REST API response object
        """

        headers = {
            "Accept": "application/" + media_type,
            "Authorization": "token " + self.token,
        }

        if media_type:
            headers["Accept"] = "application/" + media_type

        req_url = self.gh_api + url
        req = requests.get(req_url, headers=headers, params=params)

        if req.status_code not in range(200, 301):
            print(req_url, req.json())
            raise GitHubAPIException(req.status_code, req.json())

        return req.json()

    def check_rate(self, resource):
        """Helper that checks the rate limit for a given resource and pauses
           if amount is depleted for instance token.

        Args:
            resource (str): The type of resource that the rate limit is validated
            against. https://docs.github.com/en/rest/reference/rate-limit
        """
        req = self.get("/rate_limit")

        rate = req["resources"][resource]
        remaining = rate["remaining"]
        reset = rate["reset"]

        if not remaining:
            pause = (reset - time.time()) + 3
            print(f"...waiting for {pause} seconds.")
            time.sleep(pause)
            print("...resuming.")
            return


def backfill_pr_queries():
    """Generate historical GitHub queries for PRs

    Returns:
        list: list of queries
    """
    queries = []
    for repo in REPOS:
        for period in PERIODS:
            queries += [
                f"repo:aws-amplify/{repo} is:pr created:{period[0]}..{period[1]}"
            ]
    return queries


def backfill_issue_queries():
    """Generate historical GitHub queries for issues

    Returns:
        list: list of queries
    """
    queries = []
    for repo in REPOS:
        for period in ISSUE_PERIODS:
            queries += [
                f"repo:aws-amplify/{repo} is:issue created:{period[0]}..{period[1]}"
            ]
    return queries


def get_issues(gh, query):
    """Search and format issues from GitHub API.

    Args:
        gh (GitHubAPI): instance of API helper with token
        query (str): search query to pass to the REST search enpoint

    Returns:
        list: list of items matching the input query
    """
    params = {
        "q": query,
        "per_page": 100,
        "page": 1,
    }

    gh.check_rate("search")
    res = gh.get("/search/issues", **params)

    tc = res["total_count"]
    count = len(res["items"])
    issues = res["items"]

    print(f"{query} total count is : {tc}")
    gh.check_rate("search")

    while count < tc:
        params["page"] = params["page"] + 1
        res = gh.get("/search/issues", **params)
        recs = res["items"]

        if recs:
            count = count + len(recs)
            issues = issues + recs
            print(f"{count}/{tc}")
            gh.check_rate("search")
        else:
            break

    for rec in issues:
        repo = rec["repository_url"].split("/")
        rec["username"] = rec.get("username", rec["user"]["login"])
        rec["repo"] = rec.get("repo", repo[-1])
        rec["org"] = rec.get("org", repo[-2])

    return issues


def get_org_members(gh):
    """Get GitHub organization members.

    Args:
        gh (GitHubAPI): instance of API helper with token

    Returns:
        list[dict]: member list
    """
    params = {
        "per_page": 100,
        "page": 1,
    }

    gh.check_rate("core")
    mem = gh.get("/orgs/aws-amplify/members", **params)

    count = len(mem)
    org_members = mem
    if count < params["per_page"]:
        return org_members

    gh.check_rate("core")

    while count > 0:
        params["page"] = params["page"] + 1
        mem = gh.get("/orgs/aws-amplify/members", **params)
        count = len(mem)
        if count:
            org_members = org_members + mem
            gh.check_rate("core")
        else:
            break

    return org_members


def backfill_org_prs(db, gh):
    queries = backfill_pr_queries()
    for q in queries:
        prs = get_issues(gh, query=q)
        recs = [PullRequest(**rec) for rec in prs]
        db.add_all(recs)
        db.commit()
    db.close()


def backfill_org_issues(gh):
    queries = backfill_issue_queries()
    for q in queries:
        issues = get_issues(gh, query=q)
        recs = [Issue(**rec) for rec in issues]
        db.add_all(recs)
        db.commit()
    db.close()


def update_org_issues_daily(db, gh, db_model, prs=True):
    """Retrieve items created on or before today-5 days
       and store new records in db

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        db_model (sqlalchemy model): DB table model that corresponds with datatype
        prs (bool, optional): Flag to indicate whether to search
        PRs or issues. Defaults to True (i.e. search PRs).
    """
    # TODO: abstract this
    today = date.today()
    since_dt = today - timedelta(days=5)

    for repo in REPOS:
        q = f"repo:aws-amplify/{repo} created:>={since_dt}"

        if prs:
            q += " is:pr "
        else:
            q += " is:issue "

        issues = get_issues(gh, query=q)
        issue_ids = [issue["id"] for issue in issues]

        # find existing
        existing_recs = db.query(db_model).filter(db_model.id.in_(issue_ids)).all()
        existing_rec_ids = [rec.id for rec in existing_recs]

        # add new recs
        for issue in issues:
            issue_id = issue["id"]
            if issue_id not in existing_rec_ids:
                new_rec = db_model(**issue)
                db.add(new_rec)
                db.commit()
                print(f"new rec added. {issue['id']}")
        db.close()


def update_org_issues_closed_daily(db, gh, db_model, prs=True, week_interval=1):
    """Retrieve items closed on or before today-1 week
       updates existing DB record or inserts a new record.

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        db_model (sqlalchemy model): DB table model that corresponds with datatype
        prs (bool, optional): Flag to indicate whether to search
        PRs or issues. Defaults to True (i.e. search PRs).
        week_interval (int, optional): Number of historical weeks to search. Defaults to 1.
    """
    today = date.today()
    since_dt = today - timedelta(weeks=week_interval)

    for repo in REPOS:
        print(f"updating {repo}...")
        q = f"repo:aws-amplify/{repo} closed:>={since_dt}"
        if prs:
            q += " is:pr "
        else:
            q += " is:issue "

        issues = get_issues(gh, query=q)
        issue_ids = [issue["id"] for issue in issues]

        # find existing
        existing_recs = db.query(db_model).filter(db_model.id.in_(issue_ids)).all()
        existing_rec_ids = {rec.id: rec for rec in existing_recs}

        for issue in issues:
            issue_id = issue["id"]
            if issue_id in existing_rec_ids.keys():
                # check last updated date diffs between db and remote
                if (
                    issue["updated_at"]
                    != existing_rec_ids[issue_id].updated_at.isoformat() + "Z"
                ):
                    # update
                    del issue["id"]
                    db.query(db_model).filter(db_model.id == issue_id).update(
                        dict(**issue)
                    )
                    db.commit()
                    print(f"updated rec. {issue_id}")
            else:
                new_rec = db_model(**issue)
                db.add(new_rec)
                db.commit()
                print(f"new rec added. {issue['id']}")
    db.close()


def update_org_members_daily(db, gh):
    """Update GitHub organization members in the database. Insert new
       records for new members and set existing members to inactive if no longer
       in the organization.

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token

    """
    mems = get_org_members(gh)
    mems_ids = [mem["id"] for mem in mems]

    # find existing
    existing_recs = db.query(Member).filter(Member.id.in_(mems_ids)).all()
    existing_rec_ids = [rec.id for rec in existing_recs]

    # new
    for mem in mems:
        mem_id = mem["id"]
        if mem_id not in existing_rec_ids:
            new_rec = Member(**mem)
            db.add(new_rec)
            db.commit()

            # add to existing for inactive
            # record check below
            existing_rec_ids.append(mem_id)
            print(f"new member added. {mem_id}")

    # inactive
    for rec_id in existing_rec_ids:
        if rec_id not in mems_ids:
            db.query(Member).filter(Member.id == rec_id).update(
                dict(inactive_dt=datetime.now(), inactive=True)
            )
            db.commit()

    db.close()
    print("members updated.")


# run this daily
def reconcile_unmerged_closed_prs(db, gh, since_dt=None):
    """Retrieve and update all PRs that have been `closed`
       and **not** `merged` in the database. PRs have a `state` attrbute
       that only shows `open`/`closed`. For external contributors, we
       want to know if the PR was `closed` and `merged`.

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (GitHubAPI): instance of API helper with token
        since_dt (str, optional): [description]. Defaults to None.
    """
    if not since_dt:
        today = date.today()
        since_dt = today - timedelta(weeks=52)

    for repo in REPOS:
        q = f"repo:aws-amplify/{repo} is:pr is:closed is:unmerged closed:>={since_dt}"
        prs = get_issues(gh, query=q)
        pr_ids = [pr["id"] for pr in prs]

        # find prs that already exist in db that need
        # `merged` value set to false
        existing_recs = (
            db.query(PullRequest)
            .filter(PullRequest.id.in_(pr_ids), PullRequest.merged == True)
            .all()
        )
        # update existing
        for rec in existing_recs:
            rec.merged = False
            db.commit()
    db.close()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from models import Member, PullRequest, Issue, create_all, create_db_session

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---
    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)
    # ---
    # create_all(db_url)
    # backfill_org_prs(gh)
    # backfill_org_issues(gh)

    # prs
    update_org_issues_daily(db, gh, PullRequest, prs=True)
    update_org_issues_closed_daily(db, gh, PullRequest, prs=True)

    # issues
    update_org_issues_daily(db, gh, Issue, prs=False)
    update_org_issues_closed_daily(db, gh, Issue, prs=False)

    update_org_members_daily(db, gh)
    # reconcile_unmerged_closed_prs(db, gh, "2019-01-01")
