def get_org_members(gh):
    params = {
        "per_page": 100,
        "page": 1,
    }

    gh.check_rate("core")

    mem = gh.get("/orgs/aws-amplify/members", **params)

    count = len(mem)
    out = mem

    if count < params["per_page"]:
        return out

    gh.check_rate("core")

    while count > 0:
        params["page"] = params["page"] + 1

        mem = gh.get("/orgs/aws-amplify/members", **params)

        count = len(mem)
        if count:
            out = out + mem
            gh.check_rate("core")

        else:
            break

    return out
