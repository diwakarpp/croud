# Licensed to CRATE Technology GmbH ("Crate") under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  Crate licenses
# this file to you under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  You may
# obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations
# under the License.
#
# However, if you have executed another commercial license agreement
# with Crate these terms will supersede the license and you may use the
# software solely pursuant to the terms of the relevant commercial agreement.

from argparse import Namespace
from unittest import mock

import pytest

from croud.clusters.commands import clusters_list
from croud.config import Configuration, config_get, config_set
from croud.gql import Query
from croud.login import _login_url, _set_login_env, login
from croud.logout import logout
from croud.organizations.commands import organizations_create, organizations_list
from croud.organizations.users.commands import org_users_add, org_users_remove
from croud.products.deploy import product_deploy
from croud.projects.commands import project_create, projects_list
from croud.server import Server
from croud.users.commands import users_list
from croud.users.roles.commands import roles_add, roles_list, roles_remove


class TestLogin:
    @mock.patch("croud.config.Configuration.set_context")
    @mock.patch("croud.config.Configuration.override_context")
    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    @mock.patch.object(Server, "stop")
    @mock.patch.object(Server, "start")
    @mock.patch("croud.login.asyncio.get_event_loop")
    @mock.patch("croud.login.can_launch_browser", return_value=True)
    @mock.patch("croud.login.open_page_in_browser")
    @mock.patch("croud.login.print_info")
    def test_login_success(
        self,
        mock_print_info,
        mock_open_page_in_browser,
        mock_can_launch_browser,
        mock_loop,
        mock_start,
        mock_stop,
        mock_load_config,
        mock_override_context,
        mock_set_context,
    ):
        m = mock.mock_open()
        with mock.patch("croud.config.open", m, create=True):
            login(Namespace(env=None))

        calls = [
            mock.call("A browser tab has been launched for you to login."),
            mock.call("Login successful."),
        ]
        mock_print_info.assert_has_calls(calls)

    @mock.patch("croud.config.Configuration.get_env", return_value="dev")
    @mock.patch("croud.login.can_launch_browser", return_value=False)
    @mock.patch("croud.login.print_error")
    def test_login_no_valid_browser(
        self, mock_print_error, mock_can_launch_browser, mock_get_env
    ):
        with pytest.raises(SystemExit) as e_info:
            login(Namespace(env=None))

        mock_print_error.assert_called_once_with(
            "Login only works with a valid browser installed."
        )
        assert e_info.value.code == 1

    @mock.patch("croud.config.Configuration.override_context")
    @mock.patch("croud.config.Configuration.get_env", return_value="dev")
    def test_login_env_from_current_context(self, mock_get_env, mock_override_context):
        env = _set_login_env(None)
        assert env == "dev"

    def test_login_env_override_context_from_argument(self):
        env = _set_login_env("prod")
        assert env == "prod"

    def test_login_urls_from_valid_envs(self):
        url = _login_url("dev")
        assert "https://bregenz.a1.cratedb-dev.cloud/oauth2/login?cli=true" == url

        url = _login_url("prod")
        assert "https://bregenz.a1.cratedb.cloud/oauth2/login?cli=true" == url

        url = _login_url("PROD")
        assert "https://bregenz.a1.cratedb.cloud/oauth2/login?cli=true" == url

    def test_env_fallback_url(self):
        url = _login_url("invalid")
        assert "https://bregenz.a1.cratedb.cloud/oauth2/login?cli=true" == url


class TestLogout:
    @mock.patch("croud.config.Configuration.override_context")
    @mock.patch("croud.logout.Configuration.set_token")
    @mock.patch("croud.logout.print_info")
    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    def test_logout(
        self, mock_load_config, mock_print_info, mock_set_token, mock_override_context
    ):
        m = mock.mock_open()
        with mock.patch("croud.config.open", m, create=True):
            logout(Namespace(env="dev"))

        mock_set_token.assert_called_once_with("")
        mock_print_info.assert_called_once_with("You have been logged out.")


class TestConfigGet:
    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    @mock.patch("builtins.print", autospec=True, side_effect=print)
    def test_get_env(self, mock_print, mock_load_config):
        config_get(Namespace(get="env"))
        mock_print.assert_called_once_with("prod")

    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    @mock.patch("builtins.print", autospec=True, side_effect=print)
    def test_get_top_level_setting(self, mock_print, mock_load_config):
        config_get(Namespace(get="region"))
        mock_print.assert_called_once_with("bregenz.a1")


class TestConfigSet:
    @mock.patch("croud.config.write_config")
    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    def test_set_env(self, mock_load_config, mock_write_config):
        config = Configuration.DEFAULT_CONFIG
        config["auth"]["current_context"] = "prod"

        config_set(Namespace(env="prod"))
        mock_write_config.assert_called_once_with(config)

    @mock.patch("croud.config.write_config")
    @mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
    def test_set_top_level_setting(self, mock_load_config, mock_write_config):
        config = Configuration.DEFAULT_CONFIG
        config["region"] = "eastus.azure"

        config_set(Namespace(region="eastus.azure"))
        mock_write_config.assert_called_once_with(config)

        config["region"] = "bregenz.a1"


def assert_query(mock_print, expected):
    actual = mock_print.call_args[0][0]._query
    assert actual == expected


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestClusters:
    def test_list_no_pid(self, mock_execute, mock_load_config):
        query = """
{
    allClusters {
        data {
            id
            name
            numNodes
            crateVersion
            projectId
            username
            fqdn
        }
    }
}
    """

        args = Namespace(
            env=None, output_fmt="table", project_id=None, region="bregenz.a1"
        )
        with mock.patch("croud.clusters.commands.print_query") as mock_print:
            clusters_list(args)
            assert_query(mock_print, query)

    def test_list_with_pid(self, mock_execute, mock_load_config):
        query = (
            """
{
    allClusters (filter: %s) {
        data {
            id
            name
            numNodes
            crateVersion
            projectId
            username
            fqdn
        }
    }
}
    """
            % '{by: PROJECT_ID, op: EQ, value: "60d398b4-455b-49dc-bfe9-04edf5bd3eb2"}'
        )

        args = Namespace(
            env=None,
            output_fmt="table",
            project_id="60d398b4-455b-49dc-bfe9-04edf5bd3eb2",
            region="bregenz.a1",
        )
        with mock.patch("croud.clusters.commands.print_query") as mock_print:
            clusters_list(args)
            assert_query(mock_print, query)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestOrganizations:
    def test_create(self, mock_execute, mock_load_config):
        mutation = """
    mutation {
        createOrganization(input: {
            name: "testorg",
            planType: 1
        }) {
            id
            name
            planType
        }
    }
    """

        args = Namespace(env="dev", name="testorg", output_fmt="json", plan_type=1)
        with mock.patch("croud.organizations.commands.print_query") as mock_print:
            organizations_create(args)
            assert_query(mock_print, mutation)

    def test_list(self, mock_execute, mock_load_config):
        query = """
    {
        allOrganizations {
            data {
                id,
                name,
                planType,
                notification {
                    alert {
                        email,
                        enabled
                    }
                }
            }
        }
    }
    """

        args = Namespace(env="dev")
        with mock.patch("croud.organizations.commands.print_query") as mock_print:
            organizations_list(args)
            assert_query(mock_print, query)

    def test_add_user(self, mock_execute, mock_load_config):
        query = """
    mutation {
        addUserToOrganization(input: {user: "1"}) {
            user: {
                uid
                email
                organizationId
            }
        }
    }
    """

        args = Namespace(env="dev", user="1")
        with mock.patch("croud.organizations.users.commands.print_query") as mock_print:
            org_users_add(args)
            assert_query(mock_print, query)

    def test_add_user_fqn(self, mock_execute, mock_load_config):
        query = """
    mutation {
        addUserToOrganization(input: {user: "1", role_fqn: "org_admin"}) {
            user: {
                uid
                email
                organizationId
            }
        }
    }
    """

        args = Namespace(env="dev", user="1", role="org_admin")
        with mock.patch("croud.organizations.users.commands.print_query") as mock_print:
            org_users_add(args)
            assert_query(mock_print, query)

    def test_add_user_org_id(self, mock_execute, mock_load_config):
        query = """
    mutation {
        addUserToOrganization(input: {user: "1", organizationId: "abc"}) {
            user: {
                uid
                email
                organizationId
            }
        }
    }
    """

        args = Namespace(env="dev", user="1", org_id="abc")
        with mock.patch("croud.organizations.users.commands.print_query") as mock_print:
            org_users_add(args)
            assert_query(mock_print, query)

    def test_remove_user(self, mock_execute, mock_load_config):
        query = """
    mutation {
        removeUserFromOrganization(input: {uid: "1"}) {
            success
        }
    }
    """

        args = Namespace(env="dev", user="1")
        with mock.patch("croud.organizations.users.commands.print_query") as mock_print:
            org_users_remove(args)
            assert_query(mock_print, query)

    def test_remove_user_org_id(self, mock_execute, mock_load_config):
        query = """
    mutation {
        removeUserFromOrganization(input: {uid: "1", organizationId: "abc"}) {
            success
        }
    }
    """

        args = Namespace(env="dev", user="1", org_id="abc")
        with mock.patch("croud.organizations.users.commands.print_query") as mock_print:
            org_users_remove(args)
            assert_query(mock_print, query)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestProjects:
    def test_create(self, mock_execute, mock_load_config):
        mutation = """
    mutation {
        createProject(input: {
            name: "new-project",
            organizationId: "organization-id"
        }) {
            id
        }
    }
    """

        args = Namespace(
            env="dev", name="new-project", org_id="organization-id", output_fmt="json"
        )
        with mock.patch("croud.projects.commands.print_query") as mock_print:
            project_create(args)
            assert_query(mock_print, mutation)

    def test_list_projects_org_admin(self, mock_execute, mock_load_config):
        query = """
    {
        allProjects {
            data {
                id
                name
                region
                organizationId
            }
        }
    }
    """

        args = Namespace(env="dev")
        with mock.patch("croud.projects.commands.print_query") as mock_print:
            projects_list(args)
            assert_query(mock_print, query)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestUsersRoles:
    def test_add_superuser(self, mock_execute, mock_load_config):
        input_args = f'{{userId: "123",roleFqn: "admin",resourceId: "abc"}}'
        mutation = f"""
    mutation {{
        addRoleToUser(input: {input_args}) {{
            user {{
                uid,
                email,
                username,
                organizationId
            }}
        }}
    }}
    """

        args = Namespace(
            env="dev", output_fmt="json", resource="abc", role="admin", user="123"
        )
        with mock.patch("croud.users.roles.commands.print_query") as mock_print:
            roles_add(args)
            assert_query(mock_print, mutation)

    def test_remove(self, mock_query, mock_load_config):
        input_args = '{userId: "123",roleFqn: "org_member",resourceId: "abc"}'
        mutation = f"""
    mutation {{
        removeRoleFromUser(input: {input_args}) {{
            success
        }}
    }}
    """

        args = Namespace(
            env="dev", output_fmt="json", resource="abc", role="org_member", user="123"
        )
        with mock.patch("croud.users.roles.commands.print_query") as mock_print:
            roles_remove(args)
            assert_query(mock_print, mutation)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestRoles:
    def test_list(self, mock_execute, mock_load_config):
        query = """
    {
        allRoles {
            data {
                fqn
                friendlyName
            }
        }
    }
    """

        args = Namespace(env="dev")
        with mock.patch("croud.users.roles.commands.print_query") as mock_print:
            roles_list(args)
            assert_query(mock_print, query)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestUsers:
    def test_list_no_filter(self, mock_execute, mock_load_config):
        query = """
    {
        allUsers {
            data {
                uid
                email
                username
            }
        }
    }
    """

        args = Namespace(env=None, no_org=False, org_id=None, output_fmt=None)
        with mock.patch("croud.users.commands.print_query") as mock_print:
            users_list(args)
            assert_query(mock_print, query)

    def test_list_org_filter(self, mock_execute, mock_load_config):
        query = """
    {
        allUsers(queryArgs: {organizationId: "abc"}) {
            data {
                uid
                email
                username
            }
        }
    }
    """

        args = Namespace(env=None, no_org=False, org_id="abc", output_fmt=None)
        with mock.patch("croud.users.commands.print_query") as mock_print:
            users_list(args)
            assert_query(mock_print, query)

    def test_list_no_org_filter(self, mock_execute, mock_load_config):
        query = """
    {
        allUsers(queryArgs: {noOrg: true}) {
            data {
                uid
                email
                username
            }
        }
    }
    """

        args = Namespace(env=None, no_org=True, org_id=None, output_fmt=None)
        with mock.patch("croud.users.commands.print_query") as mock_print:
            users_list(args)
            assert_query(mock_print, query)

    def test_list_filter_dont_conflict(self, mock_execute, mock_load_config):
        query = """
    {
        allUsers(queryArgs: {organizationId: "abc"}) {
            data {
                uid
                email
                username
            }
        }
    }
    """

        args = Namespace(env=None, no_org=True, org_id="abc", output_fmt=None)
        with mock.patch("croud.users.commands.print_query") as mock_print:
            users_list(args)
            assert_query(mock_print, query)


@mock.patch("croud.config.load_config", return_value=Configuration.DEFAULT_CONFIG)
@mock.patch.object(Query, "execute")
class TestProductsDeploy:
    def test_deploy_product(self, mock_execute, mock_load_config):
        mutation = """
mutation {
    createProduct(
        tier: "s1",
        unit: 0,
        projectId: "proj_id",
        name: "test_product",
        cluster: {
            version: "3.1.6",
            username: "crate",
            password: "crate"
        },
        consumer: {
            eventhub: {
                connectionString: "string_connection_eventh",
                consumerGroup: "group_consumer_eventh",
                leaseStorage: {
                    connectionString: "str_conn_storage_lease",
                    container: "container_storage_lease"
                }
            },
            schema: "schema_consumer",
            table: "table_consumer"
        }
    ) {
        id,
        url
    }
}
    """

        args = Namespace(
            env="dev",
            tier="s1",
            unit=0,
            project_id="proj_id",
            product_name="test_product",
            version="3.1.6",
            username="crate",
            password="crate",
            consumer_eventhub_connection_string="string_connection_eventh",
            consumer_eventhub_consumer_group="group_consumer_eventh",
            consumer_eventhub_lease_storage_connection_string="str_conn_storage_lease",
            consumer_eventhub_lease_storage_container="container_storage_lease",
            consumer_schema="schema_consumer",
            consumer_table="table_consumer",
            output_fmt="table",
        )
        with mock.patch("croud.products.deploy.print_query") as mock_print:
            product_deploy(args)
            assert_query(mock_print, mutation)
            assert mock_print.call_args[0][0]._endpoint == "/product/graphql"
