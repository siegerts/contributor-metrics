import time
from datetime import date, timedelta

import requests

from models import Member, PullRequest
from org_members import get_org_members

# from sqlalchemy.exc import IntegrityError, ProgrammingError


repos = [
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


periods = [
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
        headers = {
            "Accept": "application/" + media_type,
            "Authorization": "token " + self.token,
        }

        if media_type:
            headers["Accept"] = "application/" + media_type

        req_url = self.gh_api + url

        req = requests.get(req_url, headers=headers, params=params)

        if req.status_code not in range(200, 301):
            raise GitHubAPIException(req.status_code, req.json())

        return req.json()

    def check_rate(self, resource):
        req = self.get("/rate_limit")

        rl = req["resources"][resource]

        remaining = rl["remaining"]
        reset = rl["reset"]

        if remaining < 1:
            t = (reset - time.time()) + 3
            print(f"...waiting for {t} seconds.")
            time.sleep(t)
            print("...resuming.")
            return


def backfill_queries():
    queries = []
    for repo in repos:
        for period in periods:
            queries += [
                f"repo:aws-amplify/{repo} is:pr created:{period[0]}..{period[1]}"
            ]
    return queries


def get_prs(gh, query="org:aws-amplify is:pr ", since_date=None):
    q = query

    if since_date:
        q += f"created:>={since_date}"

    params = {
        "q": q,
        "per_page": 100,
        "page": 1,
    }

    gh.check_rate("search")

    prs = gh.get("/search/issues", **params)

    tc = prs["total_count"]
    count = len(prs["items"])
    out = prs["items"]

    print(f"{q} total count is : {tc}")

    gh.check_rate("search")

    while count < tc:
        params["page"] = params["page"] + 1

        prs = gh.get("/search/issues", **params)
        recs = prs["items"]

        if recs:
            count = count + len(recs)
            out = out + recs
            print(count, "/", tc)

            gh.check_rate("search")

        else:
            break

    for rec in out:
        rec["username"] = rec["user"]["login"]
        repo = rec["repository_url"].split("/")
        rec["repo"] = repo[-1]
        rec["org"] = repo[-2]

    return out


def backfill_org_prs(db, gh):
    queries = backfill_queries()
    for q in queries:
        prs = get_prs(gh, query=q)
        recs = [PullRequest(**rec) for rec in prs]
        db.add_all(recs)
        db.commit()
        db.close()


# run this daily
def update_org_prs_daily(db, gh):
    today = date.today()
    since_dt = today - timedelta(days=5)
    for repo in repos:
        q = f"repo:aws-amplify/{repo} is:pr created:>={since_dt}"
        prs = get_prs(gh, query=q)
        pr_ids = [pr["id"] for pr in prs]

        # find existing
        existing_recs = db.query(PullRequest).filter(PullRequest.id.in_(pr_ids)).all()
        existing_rec_ids = [rec.id for rec in existing_recs]

        # add new recs
        for pr in prs:
            pr_id = pr["id"]
            if pr_id not in existing_rec_ids:
                new_rec = PullRequest(**pr)
                db.add(new_rec)
                db.commit()
                print(f"new rec added. {pr['id']}")

        db.close()


# run this daily
def update_org_prs_closed_daily(db, gh, week_interval=1):
    today = date.today()
    since_dt = today - timedelta(weeks=week_interval)
    for repo in repos:
        print(f"updating {repo} prs...")
        q = f"repo:aws-amplify/{repo} is:pr closed:>={since_dt}"
        prs = get_prs(gh, query=q)

        pr_ids = [pr["id"] for pr in prs]

        # find existing
        existing_recs = db.query(PullRequest).filter(PullRequest.id.in_(pr_ids)).all()

        existing_rec_ids = {rec.id: rec for rec in existing_recs}

        for pr in prs:
            pr_id = pr["id"]
            if pr_id in existing_rec_ids.keys():
                # check last updated date diffs between db and remote
                if (
                    pr["updated_at"]
                    != existing_rec_ids[pr_id].updated_at.isoformat() + "Z"
                ):

                    # update
                    del pr["id"]
                    db.query(PullRequest).filter(PullRequest.id == pr_id).update(
                        dict(**pr)
                    )
                    db.commit()
                    print(f"updated rec. {pr_id}")
            else:
                new_rec = PullRequest(**pr)
                db.add(new_rec)
                db.commit()
                print(f"new rec added. {pr['id']}")
    db.close()


# run this daily
def update_org_members_daily(db, gh):
    mems = get_org_members(gh)
    mems_ids = [mem["id"] for mem in mems]

    # find existing
    existing_recs = db.query(Member).filter(Member.id.in_(mems_ids)).all()
    existing_rec_ids = [rec.id for rec in existing_recs]

    for mem in mems:
        mem_id = mem["id"]
        if mem_id not in existing_rec_ids:
            new_rec = Member(**mem)
            db.add(new_rec)
            db.commit()
            print(f"new mem added. {mem_id}")
    db.close()
    print("members updated.")


# run this daily
def reconcile_unmerged_closed_prs(db, gh, since_dt):
    for repo in repos:
        q = f"repo:aws-amplify/{repo} is:pr is:closed is:unmerged closed:>={since_dt}"
        prs = get_prs(gh, query=q)
        print("REPO: ", repo, " COUNT: ", len(prs))

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
    from models import create_all, create_db_session
    from dotenv import load_dotenv

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---

    gh = GitHubAPI(token=token)
    db = create_db_session(db_url)

    # ---

    # create_all(db_url)
    # backfill_org_prs(gh)

    update_org_prs_daily(db, gh)
    update_org_prs_closed_daily(db, gh)
    reconcile_unmerged_closed_prs(db, gh, "2019-01-01")
    update_org_members_daily(db, gh)
