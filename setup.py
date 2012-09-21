#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2012 Kylinos <kylin7.sg@gmail.com>
#
# Author: Liyingjun <liyingjun1988gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import textwrap

import setuptools

requirements = [
    'ceilometer',
    'nova',
    'sqlalchemy',
    'eventlet',
    'argparse',
    'python-keystoneclient',
    'python-novaclient'
]

setuptools.setup(
    name = "billing",
    version = "0.1",
    description = "OpenStack Billing System",
    long_description = "OpenStack Billing System",
    url = 'https://www.kylin-os.com.cn',
    license = 'Apache',
    author = 'Kylin CG',
    author_email = 'kylin7.sg@gmail.com',
    packages = setuptools.find_packages(exclude=['bin']),
    include_package_data=True,
    scripts=['bin/billing-agent', 'bin/billing-manage', 'bin/billing-api'],
    py_modules=[],
    install_requires = requirements
)
