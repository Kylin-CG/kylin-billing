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
"""Blueprint for version 1 of API.
"""

# [ ] / -- information about this version of the API
#
# [ ] /records -- list of all records.
# [ ] /records/<id> -- get or update record by id.
# [ ] /projects/<project>/records -- get or update details of the billing
#                                    record for the project.
# [ ] /items/<id> -- get or update a item record by id.
# [ ] /projects/<project>/items -- get all item record for a project.
# [ ] /projects/<project>/items/<item>/records -- get or update item billing
#                                                 billing for the project.

import datetime

import flask
import json
import webob.exc

from billing import exception
from billing.openstack.common import log
from billing.openstack.common import timeutils

from ceilometer import storage


LOG = log.getLogger(__name__)


blueprint = flask.Blueprint('v1', __name__)


## APIs for working with resources.


@blueprint.route('/projects/<project>/records', methods=['GET', 'PUT'])
def handle_project_records(project):
    """Get or update the record of a project.
    :param project: The ID of the owning project.
    """
    db_api = flask.request.db_api
    record = {}

    if flask.request.method == 'GET':
        try:
            record=db_api.record_get_for_project(project)
        except exception.ProjectRecordNotFound:
            raise webob.exc.HTTPNotFound()

    if flask.request.method == 'PUT':
        values = json.loads(flask.request.data).get('records', None)
        # Need to format datetime from string to datetime object.
        if 'until' in values:
            values['until'] = datetime.datetime.strptime(values['until'],
                                                         "%Y-%m-%d %H:%M:%S")
        
        if values:
            try:
                # Write data to database
                record = db_api.record_update_for_project(project, values)
                LOG.info("Project bill updated: %s" % values["amount"])
            except exception.ProjectRecordNotFound:
                record = db_api.record_create_for_project(project, values)
                LOG.info("Project bill created: %s" % values["amount"])

    return flask.jsonify(records=record)


@blueprint.route('/records')
def get_all_project_records():
    """Return a list of all project records.
    """
    records = flask.request.db_api.get_all_project_record()
    return flask.jsonify(records=records)


@blueprint.route('/records/<id>', methods=['GET', 'PUT', 'DELETE'])
def handle_project_record_by_id(id):
    """Get or update the project record by id.
    :param: id: Record ID of the project.
    """
    db_api = flask.request.db_api
    record = {}

    if flask.request.method == 'GET':
        try:
            record = db_api.get_project_record_by_id(id)
        except exception.ProjectRecordNotFound:
            raise webob.exc.HTTPNotFound()

    if flask.request.method == 'DELETE':
        try:
            db_api.destroy_project_record_by_id(id)
        except exception.ProjectRecordNotFound:
            raise webob.exc.HTTPNotFound()

    if flask.request.method == 'PUT':
        values = json.loads(flask.request.data).get('records', None)
        if 'until' in values:
            values['until'] = datetime.datetime.strptime(values['until'],
                                                    "%Y-%m-%d %H:%M:%S")
        if values:
            record = db_api.record_update_for_project_by_id(id, values)

    return flask.jsonify(records=record)


@blueprint.route('/projects/<project>/items')
def get_all_item_record_for_project(project):
    """Get all item records for the project.
    Return a dict like this:
    {
      "records": {
        "cpu": [
          [
            <key>, 
            <value>
          ], 
        ], 
      }
    }
    :param project: The ID of the owning project.
    """
    db_api = flask.request.db_api
    try:
        records = db_api.get_all_item_record_for_project(project)
        items = db_api.get_all_item()
        item_dict = dict([(i.id, i) for i in items])
        record_dict = {}
        for record in records:
             record_dict[item_dict[record.item_id].name] = record
    except exception.ProjectItemRecordNotFound:
        record_dict = {}
    return flask.jsonify(records=record_dict)


@blueprint.route('/items/<id>', methods=['GET', 'PUT'])
def handle_item_record(id):
    """Get or update the item record by id.
    param id: The Item ID.
    """
    db_api = flask.request.db_api
    record = {}

    if flask.request.method == 'GET':
        try:
            record = db_api.get_project_item_record(id)
        except exception.ProjectItemRecordNotFound:
            raise webob.exc.HTTPNotFound()

    if flask.request.method == 'PUT':
        values = json.loads(flask.request.data).get('records', None)
        record = db_api.update_project_item_record_by_id(id, values)

    return flask.jsonify(records=record)


@blueprint.route('/projects/<project>/items/<item>/records',
                 methods=['GET', 'PUT'])
def handle_project_item_records(project, item):
    """Get or update the item record of a project by project_id and item name.
    :param project: The ID of the owning project.
    :param item: Item name.
    """
    db_api = flask.request.db_api
    record = {}

    if flask.request.method == 'GET':
        try:
            records = db_api.get_project_item_record_by_name(project_id=project,
                                                             item_name=item)
            record = records[0]
        except exception.ProjectItemRecordNotFound:
            raise webob.exc.HTTPNotFound()

    if flask.request.method == 'PUT':
        if item in flask.request.cfg.supported_items:
            values = json.loads(flask.request.data).get('records', None)
            # Item not exist, create it.
            if not db_api.item_get_by_name(item):
                db_api.item_create(item)

            resource = db_api.item_get_by_name(item)
            if not values:
                values = {}
            values['item_id'] = resource.id
            try:
                record = db_api.item_record_update_for_project(project, values)
            except exception.ProjectItemRecordNotFound:
                record = db_api.item_record_create_for_project(project, values)
    
    return flask.jsonify(records=record)
