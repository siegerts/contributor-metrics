"""
    transfers.py
    ~~~~~~~~~~~~

    Reconcile issues transferred between repositories.
    

"""
import os
import time
import requests
from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError


try:
    from chalicelib.github import GitHubAPI
except ModuleNotFoundError:
    from github import GitHubAPI

try:
    from chalicelib.models import (
        create_db_session,
        Issue,
        Transfer,
        Event,
        EventPoll,
    )
except ModuleNotFoundError:
    from models import (
        create_db_session,
        Issue,
        Transfer,
        Event,
        EventPoll,
    )

FIND_TRANSFERRED_ISSUES_STMT = text(
    """
SELECT * FROM public.issues WHERE username || created_at in 
(SELECT
	username || created_at as id
	FROM public.issues
	GROUP BY created_at, username
 	HAVING count(*) > 1
)
ORDER BY created_at, title, updated_at;
"""
)


class TransferAPI(GitHubAPI):
    def get_issue(self, url, allow_redirects=False, **params):
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": "token " + self.token,
        }

        req = requests.get(
            url, headers=headers, params=params, allow_redirects=allow_redirects
        )

        if req.status_code == 301:
            self.check_rate_headers(req)
            return req

        else:
            self.check_rate_headers(req)
            return None

    def check_rate_headers(self, req):
        if req.headers["x-ratelimit-remaining"] == 0:
            pause = (req.headers["x-ratelimit-reset"] - time.time()) + 3
            print(f"...waiting for {pause} seconds.")
            time.sleep(pause)
            print("...resuming.")


def delete_rec():
    pass


def reconcile_transferred_issues(db, gh):
    """Identify potential transferred issues.

    Steps through each and pings to determine if there
    is a redirect in place (i.e. it is transferred).

    The entire issue history (events) are transferred along
    with issue - so, the latest issue contains all of the
    comment events of the previous issues **but not**
    the labeling events. So, the orginal (pre-transfer)
    labels are persisted in the mapping.

    Reactions are also transferred.

    https://docs.github.com/en/issues/tracking-your-work-with-issues/transferring-an-issue-to-another-repository
    > When you transfer an issue, comments and assignees are retained.
    > The issue's labels and milestones are not retained.
    > This issue will stay on any user-owned or organization-wide
    > project boards and be removed from any repository project boards.

    Args:
        db (sqlalchemy DB session): sqlalchemy DB session
        gh (TransferAPI): instance of TransferAPI helper with token
    """
    with db as con:
        transferred_issues = con.execute(FIND_TRANSFERRED_ISSUES_STMT)

        gh.check_rate("core")

        print(f"checking duplicates issues for transfers...")

        for issue in transferred_issues:
            # if `Location` header present then this record is stale
            # send a network request , check for 301 + new location

            req = gh.get_issue(issue.url, allow_redirects=False)
            # if req, then the issue has moved.
            # this issue will get picked up along with
            # new issues since the updated date will change

            if req:
                # issue has moved
                new_url = req.headers.get("Location", None)

                if req.status_code == 301 and new_url:
                    print("--- issue transfer ---")
                    issue_id = issue.id
                    new_number = int(new_url.split("/")[-1])
                    new_repo = new_url.split("/")[-3]

                    new_issue = (
                        db.query(Issue)
                        .filter(Issue.number == new_number, Issue.repo == new_repo)
                        .first()
                    )

                    # the transferred issue exists in the db
                    if new_issue:
                        print(f"transferred issue found {new_issue.id}.")
                        transfer = {
                            "issue_id": issue_id,
                            "url": issue.url,
                            "number": issue.number,
                            "repo": issue.repo,
                            "title": issue.title,
                            "body": issue.body,
                            "created_at": issue.created_at,
                            "state": issue.state,
                            "closed_at": issue.closed_at,
                            "org": issue.org,
                            "assignee": issue.assignee,
                            "assignees": issue.assignees,
                            "labels": issue.labels,
                            "new_issue_id": new_issue.id,
                            "new_repo": new_issue.repo,
                            "new_url": new_issue.url,
                            "new_html_url": new_issue.html_url,
                            "new_number": new_issue.number,
                            "user": issue.user,
                            "username": issue.username,
                        }

                        new_rec = Transfer(**transfer)
                        db.add(new_rec)

                        try:
                            db.commit()
                        except IntegrityError:
                            db.rollback()
                            print(f"transferred issue already exists {new_issue.id}.")
                            continue

                        # delete rec and all associations
                        print(f"removing {issue_id}...")

                        # delete issue events
                        related_events = (
                            db.query(Event).filter(Event.issue_id == issue_id).delete()
                        )
                        db.commit()
                        print(
                            f"{related_events} related events deleted for rec id {issue_id}."
                        )

                        # delete issue event polls
                        related_event_polls = (
                            db.query(EventPoll)
                            .filter(EventPoll.id == issue_id)
                            .delete()
                        )
                        db.commit()
                        print(
                            f"{related_event_polls} related polls deleted for rec id {issue_id}."
                        )

                        # delete issue
                        db.query(Issue).filter(Issue.id == issue_id).delete()
                        db.commit()
                        print(f"stale issue deleted {issue_id}.\n---\n")

                    else:
                        # for now, we'll wait until the issue
                        # shows in the next pull
                        print(
                            f"transferred issue not found {new_repo}/issues/{new_number} for {issue_id}.\n---\n"
                        )

                else:
                    print(
                        f"issue returned 301 but no redirect location present {issue.id}.\n---\n"
                    )

            else:
                # issue is not transferred
                # most likely, the issue that the original was
                # transferred to
                print(f"issue was not transferred {issue.id}\n---\n")
    print("done")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    token = os.getenv("GH_TOKEN")
    db_url = os.getenv("DB_URL")

    # ---
    gh = TransferAPI(token=token)
    db = create_db_session(db_url)

    reconcile_transferred_issues(db, gh)
