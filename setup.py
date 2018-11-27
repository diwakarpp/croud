#!/usr/bin/env python
#
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

from setuptools import setup

try:
    with open("README.rst", "r", encoding="utf-8") as f:
        readme = f.read()
except IOError:
    readme = ""


setup(
    name="croud",
    author="CRATE Technology GmbH",
    author_email="office@crate.io",
    url="https://github.com/crate/croud",
    description="A command line interface for CrateDB Cloud",
    long_description=readme,
    entry_points={
        "console_scripts": ["croud = croud.__main__:main"],
        "croud_commands": [
            "login = croud.login:login",
            "logout = croud.logout:logout",
            "me = croud.me:me",
        ],
    },
    packages=["croud"],
    install_requires=[
        "argh",
        "aiohttp",
        "colorama",
        "appdirs",
        "pyyaml",
        "certifi",
        "tabulate",
    ],
    extras_require={
        "testing": [
            "pytest>=3,<4",
            "pytest-flake8",
            "pytest-mock",
            "pytest-isort",
            "pytest-black",
            "pytest-mypy",
            "pytest-aiohttp",
            "mypy",
            "black",
        ],
        "development": ["black"],
    },
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Database",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
)
