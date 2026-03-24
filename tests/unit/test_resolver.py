"""Unit tests for CLI resource reference resolver."""

from unittest.mock import patch

import click
import pytest

from mob.cli.resolver import resolve_ref


ORGS = [
    {"id": "aaa-111", "identifier": "acme-corp", "name": "Acme Corp"},
    {"id": "bbb-222", "identifier": "widgets-inc", "name": "Widgets Inc"},
    {"id": "ccc-333", "identifier": "mega-co", "name": "Mega Co"},
]

AGENTS = [
    {"id": "ag-1", "name": "coder", "domain_id": "dom-1"},
    {"id": "ag-2", "name": "coder", "domain_id": "dom-2"},
    {"id": "ag-3", "name": "reviewer", "domain_id": "dom-1"},
]

USERS = [
    {"id": "u-1", "email": "alice@example.com", "name": "Alice"},
    {"id": "u-2", "email": "bob@example.com", "name": "Bob"},
]

SKILLS = [
    {"id": "sk-1", "name": "code-review", "description": "Reviews code"},
    {"id": "sk-2", "name": "testing", "description": "Writes tests"},
]

GROUPS = [
    {"id": "g-1", "name": "eng", "organization_id": "aaa-111"},
    {"id": "g-2", "name": "eng", "organization_id": "bbb-222"},
    {"id": "g-3", "name": "design", "organization_id": "aaa-111"},
]


class TestResolveByUUID:
    """UUID passthrough."""

    def test_uuid_returned_directly(self):
        uuid = "12345678-1234-1234-1234-123456789abc"
        assert resolve_ref("organization", uuid) == uuid

    def test_uppercase_uuid(self):
        uuid = "12345678-1234-1234-1234-123456789ABC"
        assert resolve_ref("organization", uuid) == uuid


class TestResolveByPosition:
    """Positional index resolution."""

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_position_1(self, mock_get):
        assert resolve_ref("organization", "1") == "aaa-111"
        mock_get.assert_called_with("/organizations", params=None)

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_position_3(self, mock_get):
        assert resolve_ref("organization", "3") == "ccc-333"

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_position_out_of_range(self, mock_get):
        with pytest.raises(click.ClickException, match="Position 5 is out of range"):
            resolve_ref("organization", "5")

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_position_zero_out_of_range(self, mock_get):
        with pytest.raises(click.ClickException, match="Position 0 is out of range"):
            resolve_ref("organization", "0")

    @patch("mob.cli.resolver.api_get", return_value=[])
    def test_position_on_empty_list(self, mock_get):
        with pytest.raises(click.ClickException, match="list is empty"):
            resolve_ref("organization", "1")

    @patch("mob.cli.resolver.api_get", return_value=AGENTS[:1])
    def test_position_with_filters(self, mock_get):
        result = resolve_ref("agent", "1", domain_id="dom-1")
        assert result == "ag-1"
        mock_get.assert_called_with("/agents", params={"domain_id": "dom-1"})


class TestResolveByName:
    """Name/identifier lookup."""

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_org_by_identifier(self, mock_get):
        assert resolve_ref("organization", "acme-corp") == "aaa-111"

    @patch("mob.cli.resolver.api_get", return_value=USERS)
    def test_user_by_email(self, mock_get):
        assert resolve_ref("user", "alice@example.com") == "u-1"

    @patch("mob.cli.resolver.api_get", return_value=SKILLS)
    def test_skill_by_name(self, mock_get):
        assert resolve_ref("skill", "code-review") == "sk-1"

    @patch("mob.cli.resolver.api_get", return_value=ORGS)
    def test_name_not_found(self, mock_get):
        with pytest.raises(click.ClickException, match="No organization with identifier 'nonexistent'"):
            resolve_ref("organization", "nonexistent")


class TestScopedResolution:
    """Scoped name resolution (groups, agents)."""

    @patch("mob.cli.resolver.api_get")
    def test_agent_unique_with_domain_filter(self, mock_get):
        # When filtered by domain, only one "coder" matches
        mock_get.return_value = [AGENTS[0]]  # just ag-1
        result = resolve_ref("agent", "coder", domain_id="dom-1")
        assert result == "ag-1"
        mock_get.assert_called_with("/agents", params={"domain_id": "dom-1"})

    @patch("mob.cli.resolver.api_get")
    def test_agent_ambiguous_without_filter(self, mock_get):
        # Without filter, two "coder" agents match
        mock_get.return_value = AGENTS  # all agents, two named "coder"
        with pytest.raises(click.ClickException, match="Multiple agents match"):
            resolve_ref("agent", "coder")

    @patch("mob.cli.resolver.api_get")
    def test_group_ambiguous_without_org(self, mock_get):
        # Without org filter, two "eng" groups
        mock_get.return_value = GROUPS
        with pytest.raises(click.ClickException, match="Multiple groups match"):
            resolve_ref("group", "eng")

    @patch("mob.cli.resolver.api_get")
    def test_group_unique_with_org_filter(self, mock_get):
        mock_get.return_value = [GROUPS[0]]  # just g-1
        result = resolve_ref("group", "eng", organization_id="aaa-111")
        assert result == "g-1"

    @patch("mob.cli.resolver.api_get")
    def test_ambiguity_error_suggests_flag(self, mock_get):
        mock_get.return_value = AGENTS
        with pytest.raises(click.ClickException, match="--domain"):
            resolve_ref("agent", "coder")

    @patch("mob.cli.resolver.api_get")
    def test_group_ambiguity_suggests_org_flag(self, mock_get):
        mock_get.return_value = GROUPS
        with pytest.raises(click.ClickException, match="--org"):
            resolve_ref("group", "eng")

    @patch("mob.cli.resolver.api_get")
    def test_name_not_found_with_filter_tries_global(self, mock_get):
        # Filtered list returns empty, global list has a unique match
        mock_get.side_effect = [
            [],          # filtered call returns empty
            [GROUPS[2]], # global call finds "design" uniquely
        ]
        result = resolve_ref("group", "design", organization_id="bbb-222")
        assert result == "g-3"

    @patch("mob.cli.resolver.api_get")
    def test_name_not_found_globally_either(self, mock_get):
        mock_get.side_effect = [
            [],  # filtered
            [],  # global
        ]
        with pytest.raises(click.ClickException, match="No group with name 'nope'"):
            resolve_ref("group", "nope", organization_id="aaa-111")


class TestUnknownResourceType:
    def test_unknown_type(self):
        with pytest.raises(click.ClickException, match="Unknown resource type"):
            resolve_ref("widget", "foo")
