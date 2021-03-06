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

"""
Kylin-billing exception subclasses
"""

import urlparse

class RedirectException(Exception):
    def __init__(self, url):
        self.url = urlparse.urlparse(url)


class BillingException(Exception):
    """
    Base Billing Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.
    """
    message = "An unknown exception occurred"

    def __init__(self, message=None, *args, **kwargs):
        if not message:
            message = self.message
        try:
            message = message % kwargs
        except Exception:
            # at least get the core message out if something happened
            pass
        super(BillingException, self).__init__(message)


class DatabaseMigrationError(BillingException):
    message = "There was an error migrating the database."


class MissingArgumentError(BillingException):
    message = "Missing required argument."


class ProjectRecordNotFound(BillingException):
    message = "Project account record not found."


class ProjectItemRecordNotFound(BillingException):
    message = "Project item record not found."


class ItemNotSupported(BillingException):
    message = "Item: %(item)s not supported."


class ServiceCatalogException(BillingException):
    """
    Raised when a requested service is not available in the ``ServiceCatalog``
    returned by Keystone.
    """
    def __init__(self, service_name):
        message = 'Invalid service catalog service: %s' % service_name
        super(ServiceCatalogException, self).__init__(message)
