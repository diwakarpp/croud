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

import ssl
from types import TracebackType
from typing import Dict, Optional, Type

import certifi
from aiohttp import ClientSession, ContentTypeError, TCPConnector  # type: ignore

from croud.config import Configuration
from croud.printer import print_error
from croud.typing import JsonDict

CLOUD_DEV_DOMAIN: str = "cratedb-dev.cloud"
CLOUD_PROD_DOMAIN: str = "cratedb.cloud"


class HttpSession:
    def __init__(
        self,
        region: str = "bregenz.a1",
        env: str = "prod",
        url: Optional[str] = None,
        conn: Optional[TCPConnector] = None,
        headers: Dict[str, str] = {},
    ) -> None:
        if not url:
            host = CLOUD_PROD_DOMAIN
            if env.lower() == "dev":
                host = CLOUD_DEV_DOMAIN
            url = f"https://{region}.{host}/graphql"

        self.url = url

        token = Configuration.read_token()

        if conn is None:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            conn = TCPConnector(ssl_context=ssl_context)

        self.client = ClientSession(
            cookies={"session": token}, connector=conn, headers=headers
        )

    async def fetch(self, query: str) -> JsonDict:
        resp = await self.client.post(self.url, json={"query": query})
        if resp.status == 200:
            try:
                result = await resp.json()
                return result["data"]
            except ContentTypeError:
                print_error(
                    "Unauthorized. Use `croud login` to login to CrateDB Cloud."
                )
                await self.client.close()
                exit(1)
        else:
            raise Exception(
                f"Query failed to run by returning code of {resp.status}. {query}"
            )

    async def __aenter__(self) -> "HttpSession":
        return self

    async def close(self) -> None:
        await self.client.close()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()