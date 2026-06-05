from .it_agent import process as it_agent
from .hr_agent import process as hr_agent
from .approval_agent import process as approval_agent
from .knowledge_agent import process as knowledge_agent
from .ai_agent import process as ai_agent
from .leave_agent import process as leave_agent
from .policy_agent import process as policy_agent

def orchestrate(user_request):

    text = user_request.lower()
    results = []

    if "laptop" in text:
        results.append(it_agent())
        results.append(knowledge_agent("laptop"))

    if "vpn" in text:
        results.append(approval_agent())
        results.append(knowledge_agent("vpn"))

    if "project" in text or "joining" in text or "onboarding" in text:
        results.append(hr_agent())

    if (
        "leave" in text
        or "pto" in text
        or "vacation" in text
        or "time off" in text
        or "sick day" in text
    ):
        results.append(leave_agent(user_request))

    if (
        "policy" in text
        or "housing" in text
        or "mobile" in text
        or "broadband" in text
        or "expense" in text
        or "reimbursement" in text
    ):
        results.append(policy_agent(user_request))

    if not results:
        results.append(ai_agent(user_request))

    return results
