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

from unittest import mock

import aiohttp
import pytest
from aiohttp.test_utils import loop_context
from util.fake_server import FakeCrateDBCloud, FakeResolver

from croud.config import Configuration
from croud.session import HttpSession, cloud_url

me_query = """
{
  me {
    email
    username
    name
  }
}
"""

me_response = {
    "me": {
        "email": "sheldon@crate.io",
        "username": "Google_1234",
        "name": "Sheldon Cooper",
    }
}


@mock.patch.object(Configuration, "get_env", return_value="dev")
class TestHttpSession:
    @pytest.mark.parametrize("variables", [None, {"a": "foo", "b": 42}])
    @mock.patch.object(Configuration, "get_token", return_value="eyJraWQiOiIx")
    def test_query_success(self, mock_token, mock_env, variables):
        with loop_context() as loop:

            # Takes a query that will be used to determine which response is
            # generated by the FakeCrateDBCloud instance
            async def test_query(headers_query: dict):
                env = Configuration.get_env()
                token = Configuration.get_token()
                async with HttpSession(
                    env,
                    token,
                    url="https://cratedb.local",
                    conn=connector,
                    headers=headers_query,  # Determines the generated response
                ) as session:
                    result = await session.fetch(me_query, variables)
                    assert result["data"] == me_response

            fake_cloud = FakeCrateDBCloud(loop=loop)
            info = loop.run_until_complete(fake_cloud.start())
            resolver = FakeResolver(info, loop=loop)
            connector = aiohttp.TCPConnector(loop=loop, resolver=resolver, ssl=True)

            query = {"query": "me"}
            loop.run_until_complete(test_query(query))
            loop.run_until_complete(fake_cloud.stop())

    @mock.patch.object(Configuration, "get_token", return_value="")
    @mock.patch("croud.session.print_error")
    def test_query_unauthorized(self, mock_print_error, mock_token, mock_env):
        with loop_context() as loop:

            # Takes a query that will be used to determine which response is
            # generated by the FakeCrateDBCloud instance
            async def test_query(headers_query: dict):
                env = Configuration.get_env()
                token = Configuration.get_token()
                with pytest.raises(SystemExit) as cm:
                    async with HttpSession(
                        env,
                        token,
                        url="https://cratedb.local",
                        conn=connector,
                        headers=headers_query,  # Determines the generated response
                    ) as session:
                        await session.fetch(me_query, variables={})
                mock_print_error.assert_called_once_with(
                    "Unauthorized. Use `croud login` to login to CrateDB Cloud."
                )
                assert cm.value.code == 1

            fake_cloud = FakeCrateDBCloud(loop=loop)
            info = loop.run_until_complete(fake_cloud.start())
            resolver = FakeResolver(info, loop=loop)
            connector = aiohttp.TCPConnector(loop=loop, resolver=resolver, ssl=True)

            query = {"query": "me"}
            loop.run_until_complete(test_query(query))
            loop.run_until_complete(fake_cloud.stop())

    @mock.patch.object(Configuration, "get_token", return_value="eyJraWQiOiIx")
    @mock.patch("croud.session.print_info")
    def test_query_failed(self, mock_print_info, mock_token, mock_env):
        with loop_context() as loop:

            # Takes a query that will be used to determine which response is
            # generated by the FakeCrateDBCloud instance
            async def test_query(headers_query: dict):
                env = Configuration.get_env()
                token = Configuration.get_token()
                async with HttpSession(
                    env,
                    token,
                    url="https://cratedb.local",
                    conn=connector,
                    headers=headers_query,  # Determines the generated response
                ) as session:
                    query = """
                    badRequest {
                        data {
                            fakeData
                        }
                    }
                    """
                    await session.fetch(query, variables={})
                    mock_print_info.assert_has_calls([mock.call(query)])

            fake_cloud = FakeCrateDBCloud(loop=loop)
            info = loop.run_until_complete(fake_cloud.start())
            resolver = FakeResolver(info, loop=loop)
            connector = aiohttp.TCPConnector(loop=loop, resolver=resolver, ssl=True)

            query = {"query": "badRequest"}
            loop.run_until_complete(test_query(query))
            loop.run_until_complete(fake_cloud.stop())

    def test_correct_url(self, mock_env):
        region = "bregenz.a1"

        url = cloud_url("prod", region)
        assert url == f"https://{region}.cratedb.cloud"

        url = cloud_url("dev", region)
        assert url == f"https://{region}.cratedb-dev.cloud"

        url = cloud_url("local", region)
        assert url == "http://localhost:8000"

        region = "westeurope.azure"
        url = cloud_url("prod", region)
        assert url == f"https://{region}.cratedb.cloud"
