"""GraphQL client for Linear API."""

from __future__ import annotations

import os
import sys
from typing import Any, Self

import httpx

from kctl_linear.core.exceptions import APIError, AuthenticationError, ConfigError, ConnectionError


class LinearClient:
    """GraphQL client for Linear API.

    Linear uses a single POST /graphql endpoint. Auth is ``Authorization: {api_key}``
    (no Bearer prefix). This client does NOT subclass APIClient because Linear is
    GraphQL-only, not REST.
    """

    BASE_URL = "https://api.linear.app"

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key or not api_key.strip():
            raise ConfigError("Linear API key is required")

        self._api_key = api_key
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def query(self, graphql: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query and return the ``data`` dict.

        Raises:
            AuthenticationError: On 401/403 responses.
            APIError: On GraphQL-level errors or non-2xx responses.
            ConnectionError: On network failures.
        """
        payload: dict[str, Any] = {"query": graphql}
        if variables:
            payload["variables"] = variables

        try:
            self._log_debug(f"POST /graphql | variables={variables}")
            response = self._client.post("/graphql", json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ConnectionError(url=self.BASE_URL, cause=exc) from exc

        if response.status_code in (401, 403):
            raise AuthenticationError("Invalid or expired Linear API key")

        if response.status_code >= 400:
            detail = response.text[:200] if response.text else f"HTTP {response.status_code}"
            raise APIError(status_code=response.status_code, detail=detail)

        data: dict[str, Any] = response.json()

        if "errors" in data:
            errors = data["errors"]
            msg = errors[0]["message"] if errors else "Unknown GraphQL error"
            raise APIError(detail=msg)

        return data.get("data", {})

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def viewer(self) -> dict[str, Any]:
        """Return the authenticated user (viewer)."""
        return self.query(VIEWER_QUERY)["viewer"]

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    # ------------------------------------------------------------------
    # Debug logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_debug(msg: str) -> None:
        """Print debug info to stderr when KCTL_DEBUG is set."""
        if os.environ.get("KCTL_DEBUG"):
            print(f"[DEBUG] LinearClient: {msg}", file=sys.stderr)  # noqa: T201


# ======================================================================
# GraphQL query strings
# ======================================================================

VIEWER_QUERY = """\
query {
  viewer {
    id
    name
    email
    admin
    active
  }
}
"""

ISSUES_LIST_QUERY = """\
query IssuesList($teamKey: String, $state: String, $assigneeId: ID, $first: Int = 50) {
  issues(
    first: $first
    filter: {
      team: { key: { eq: $teamKey } }
      state: { name: { eq: $state } }
      assignee: { id: { eq: $assigneeId } }
    }
  ) {
    nodes {
      id
      identifier
      title
      priority
      state { name color }
      assignee { name email }
      createdAt
      updatedAt
    }
  }
}
"""

ISSUE_SHOW_QUERY = """\
query IssueShow($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    priority
    priorityLabel
    estimate
    url
    state { name color }
    assignee { id name email }
    team { key name }
    labels { nodes { name color } }
    project { name }
    cycle { name number }
    comments { nodes { body createdAt user { name } } }
    createdAt
    updatedAt
  }
}
"""

ISSUE_CREATE_MUTATION = """\
mutation IssueCreate(
  $teamId: String!, $title: String!, $description: String,
  $priority: Int, $assigneeId: String, $labelIds: [String!]
) {
  issueCreate(input: {
    teamId: $teamId
    title: $title
    description: $description
    priority: $priority
    assigneeId: $assigneeId
    labelIds: $labelIds
  }) {
    success
    issue {
      id
      identifier
      title
      url
      state { name }
    }
  }
}
"""

ISSUE_UPDATE_MUTATION = """\
mutation IssueUpdate(
  $id: String!, $stateId: String, $assigneeId: String,
  $priority: Int, $title: String, $description: String
) {
  issueUpdate(id: $id, input: {
    stateId: $stateId
    assigneeId: $assigneeId
    priority: $priority
    title: $title
    description: $description
  }) {
    success
    issue {
      id
      identifier
      title
      state { name }
      assignee { name }
    }
  }
}
"""

COMMENT_CREATE_MUTATION = """\
mutation CommentCreate($issueId: String!, $body: String!) {
  commentCreate(input: {
    issueId: $issueId
    body: $body
  }) {
    success
    comment {
      id
      body
      createdAt
      user { name }
    }
  }
}
"""

ISSUE_SEARCH_QUERY = """\
query SearchIssues($term: String!, $first: Int = 50) {
  searchIssues(term: $term, first: $first) {
    nodes {
      id
      identifier
      title
      priority
      state { name color }
      assignee { name }
      updatedAt
    }
  }
}
"""

CYCLES_LIST_QUERY = """\
query CyclesList($teamKey: String, $first: Int = 20) {
  cycles(
    first: $first
    filter: { team: { key: { eq: $teamKey } } }
    orderBy: createdAt
  ) {
    nodes {
      id
      number
      name
      startsAt
      endsAt
      progress
    }
  }
}
"""

CYCLE_CURRENT_QUERY = """\
query CycleCurrent($teamKey: String) {
  cycles(
    first: 1
    filter: {
      team: { key: { eq: $teamKey } }
      isActive: { eq: true }
    }
  ) {
    nodes {
      id
      number
      name
      startsAt
      endsAt
      progress
      issues {
        nodes {
          id
          identifier
          title
          state { name }
          assignee { name }
          priority
        }
      }
    }
  }
}
"""

CYCLE_SHOW_QUERY = """\
query CycleShow($id: String!) {
  cycle(id: $id) {
    id
    number
    name
    startsAt
    endsAt
    progress
    issues {
      nodes {
        id
        identifier
        title
        state { name color }
        assignee { name }
        priority
        estimate
      }
    }
  }
}
"""

PROJECTS_LIST_QUERY = """\
query ProjectsList($first: Int = 50) {
  projects(first: $first, orderBy: updatedAt) {
    nodes {
      id
      name
      state
      progress
      startDate
      targetDate
      lead { name }
      teams { nodes { key name } }
      updatedAt
    }
  }
}
"""

PROJECT_SHOW_QUERY = """\
query ProjectShow($id: String!) {
  project(id: $id) {
    id
    name
    description
    state
    progress
    startDate
    targetDate
    url
    lead { name email }
    members { nodes { name email } }
    teams { nodes { key name } }
    projectMilestones { nodes { name targetDate } }
    issues {
      nodes {
        id
        identifier
        title
        state { name }
        assignee { name }
      }
    }
  }
}
"""

TEAMS_LIST_QUERY = """\
query TeamsList {
  teams {
    nodes {
      id
      key
      name
      description
      members { nodes { id } }
      timezone
    }
  }
}
"""

TEAM_SHOW_QUERY = """\
query TeamShow($id: String!) {
  team(id: $id) {
    id
    key
    name
    description
    timezone
    members { nodes { id name email admin active } }
    states { nodes { name color position type } }
    labels { nodes { name color } }
  }
}
"""

LABELS_LIST_QUERY = """\
query LabelsList($teamKey: String) {
  issueLabels(
    filter: { team: { key: { eq: $teamKey } } }
  ) {
    nodes {
      id
      name
      color
      parent { name }
    }
  }
}
"""

LABEL_CREATE_MUTATION = """\
mutation LabelCreate($teamId: String, $name: String!, $color: String) {
  issueLabelCreate(input: {
    teamId: $teamId
    name: $name
    color: $color
  }) {
    success
    issueLabel {
      id
      name
      color
    }
  }
}
"""

USERS_LIST_QUERY = """\
query UsersList {
  users {
    nodes {
      id
      name
      email
      admin
      active
      displayName
    }
  }
}
"""

DASHBOARD_QUERY = """\
query Dashboard($teamKey: String) {
  viewer {
    id
    name
    email
    assignedIssues(
      first: 10
      filter: { state: { type: { nin: ["completed", "canceled"] } } }
    ) {
      nodes {
        id
        identifier
        title
        priority
        state { name color }
        updatedAt
      }
    }
  }
  cycles(
    first: 1
    filter: {
      team: { key: { eq: $teamKey } }
      isActive: { eq: true }
    }
  ) {
    nodes {
      id
      number
      name
      progress
      startsAt
      endsAt
    }
  }
  projects(first: 5, filter: { state: { eq: "started" } }) {
    nodes {
      name
      progress
      targetDate
    }
  }
}
"""

TEAM_BY_KEY_QUERY = """\
query TeamByKey($key: String!) {
  teams(filter: { key: { eq: $key } }) {
    nodes {
      id
      key
      name
    }
  }
}
"""

USER_BY_NAME_QUERY = """\
query UserByName($name: String!) {
  users(filter: { displayName: { containsIgnoreCase: $name } }) {
    nodes {
      id
      name
      email
    }
  }
}
"""

WORKFLOW_STATE_QUERY = """\
query WorkflowState($teamKey: String!, $stateName: String!) {
  workflowStates(
    filter: {
      team: { key: { eq: $teamKey } }
      name: { eqIgnoreCase: $stateName }
    }
  ) {
    nodes {
      id
      name
      type
    }
  }
}
"""
