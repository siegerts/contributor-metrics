REPOS = [
    "amplify-cli",
    "amplify-js",
    "amplify-ui",
    "amplify-hosting",
    "amplify-codegen",
    "amplify-studio",  # switched from amplify-adminui 1/3/2023
    "amplify-flutter",
    "amplify-swift",  # added 10/17/2022
    "amplify-android",
    "amplify-category-api",
    "docs",  # added 5/2/2022
]

# https://docs.github.com/en/developers/webhooks-and-events/events/issue-event-types
TRACKED_ISSUE_EVENTS = [
    "added_to_project",  #
    "assigned",  #
    # "automatic_base_change_failed",
    # "automatic_base_change_succeeded",
    # "base_ref_changed",
    "closed",  #
    "commented",  #
    # "committed",
    "connected",  #
    "convert_to_draft",  # pr
    "converted_note_to_issue",  #
    "converted_to_discussion",  #
    # "cross-referenced", # does not have a unique id
    "demilestoned",  #
    # "deployed",
    # "deployment_environment_changed",
    "disconnected",  #
    # "head_ref_deleted",
    # "head_ref_restored",
    # "head_ref_force_pushed",
    "labeled",  #
    "locked",  #
    "mentioned",  #
    "marked_as_duplicate",  #
    "merged",  # pr notify when their pr was merged!
    "milestoned",  #
    "moved_columns_in_project",  #
    "pinned",  #
    "ready_for_review",  # pr
    "referenced",  #
    "removed_from_project",  #
    "renamed",  #
    "reopened",  #
    "review_dismissed",  # pr
    "review_requested",  # pr
    "review_request_removed",  # pr
    "reviewed",  # contains user, not actor
    "subscribed",  #
    "transferred",  #
    "unassigned",  #
    "unlabeled",  #
    "unlocked",  #
    "unmarked_as_duplicate",  #
    "unpinned",  #
    "unsubscribed",  #
    "user_blocked",
]
