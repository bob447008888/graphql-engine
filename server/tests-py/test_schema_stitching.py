#!/usr/bin/env python3

import string
import random
import yaml
import json
import queue
import requests

import pytest

from validate import check_query_f, check_query


def mk_add_remote_q(name, url):
    return {
        "type": "add_remote_schema",
        "args": {
            "name": name,
            "comment": "testing " + name,
            "definition": {
                "url": url,
                "forward_client_headers": False
            }
        }
    }

def mk_delete_remote_q(name):
    return {
        "type" : "remove_remote_schema",
        "args" : {
            "name": name
        }
    }


class TestRemoteSchemaBasic:
    """ basic => no hasura tables are tracked """

    teardown = {"type": "clear_metadata", "args": {}}
    dir = 'queries/remote_schemas'

    @pytest.fixture(autouse=True)
    def transact(self, hge_ctx):
        q = mk_add_remote_q('simple 1', 'http://localhost:5000/hello-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        yield
        hge_ctx.v1q(self.teardown)

    def test_add_schema(self, hge_ctx):
        """ check if the remote schema is added in the db """
        conn = hge_ctx.engine.connect()
        res = conn.execute('select * from hdb_catalog.remote_schemas')
        row = res.fetchone()
        assert row['name'] == "simple 1"
        conn.close()

    def test_introspection(self, hge_ctx):
        #check_query_f(hge_ctx, 'queries/graphql_introspection/introspection.yaml')
        with open('queries/graphql_introspection/introspection.yaml') as f:
            query = yaml.load(f)
        st_code, resp = check_query(hge_ctx, query)
        assert st_code == 200, resp
        assert check_introspection_result(resp, ['Hello'], ['hello'])
#

    def test_introspection_as_user(self, hge_ctx):
        check_query_f(hge_ctx, 'queries/graphql_introspection/introspection_user_role.yaml')

    def test_remote_query(self, hge_ctx):
        check_query_f(hge_ctx, self.dir + '/basic_query.yaml')

    def test_remote_subscription(self, hge_ctx):
        check_query_f(hge_ctx, self.dir + '/basic_subscription_not_supported.yaml')

    def test_add_schema_conflicts(self, hge_ctx):
        """add 2 remote schemas with same node or types"""
        q = mk_add_remote_q('simple 2', 'http://localhost:5000/hello-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 400
        assert resp['code'] == 'remote-schema-conflicts'

    def test_add_second_remote_schema(self, hge_ctx):
        """add 2 remote schemas with different node and types"""
        q = mk_add_remote_q('my remote', 'http://localhost:5000/user-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        hge_ctx.v1q({"type": "remove_remote_schema", "args": {"name": "my remote"}})
        assert st_code == 200, resp

    def test_add_remote_schema_with_interfaces(self, hge_ctx):
        """add a remote schema with interfaces in it"""
        q = mk_add_remote_q('my remote interface one', 'http://localhost:5000/character-iface-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        check_query_f(hge_ctx, self.dir + '/character_interface_query.yaml')
        hge_ctx.v1q({"type": "remove_remote_schema",
                     "args": {"name": "my remote interface one"}})
        assert st_code == 200, resp

    def test_add_remote_schema_with_interface_err_empty_fields_list(self, hge_ctx):
        """add a remote schema with an interface having no fields"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_iface_err_empty_fields_list.yaml')

    def test_add_remote_schema_err_unknown_interface(self, hge_ctx):
        """add a remote schema with an interface having no fields"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_err_unknown_interface.yaml')

    def test_add_remote_schema_with_interface_err_missing_field(self, hge_ctx):
        """ add a remote schema where an object implementing an interface does
        not have a field defined in the interface """
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_err_missing_field.yaml')

    def test_add_remote_schema_with_interface_err_wrong_field_type(self, hge_ctx):
        """add a remote schema where an object implementing an interface have a
        field with the same name as in the interface, but of different type"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_iface_err_wrong_field_type.yaml')

    def test_add_remote_schema_with_interface_err_missing_arg(self, hge_ctx):
        """add a remote schema where a field of an object implementing an
        interface does not have the argument defined in the same field of
        interface"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_err_missing_arg.yaml')

    def test_add_remote_schema_with_interface_err_wrong_arg_type(self, hge_ctx):
        """add a remote schema where the argument of a field of an object
        implementing the interface does not have the same type as the argument
        defined in the field of interface"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_iface_err_wrong_arg_type.yaml')

    def test_add_remote_schema_with_interface_err_extra_non_null_arg(self, hge_ctx):
        """add a remote schema with a field of an object implementing interface
        having extra non_null argument"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_iface_err_extra_non_null_arg.yaml')

    def test_add_remote_schema_with_union(self, hge_ctx):
        """add a remote schema with union in it"""
        q = mk_add_remote_q('my remote union one', 'http://localhost:5000/union-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        check_query_f(hge_ctx, self.dir + '/search_union_type_query.yaml')
        hge_ctx.v1q({"type": "remove_remote_schema", "args": {"name": "my remote union one"}})
        assert st_code == 200, resp

    def test_add_remote_schema_with_union_err_no_member_types(self, hge_ctx):
        """add a remote schema with a union having no member types"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_union_err_no_member_types.yaml')

    def test_add_remote_schema_with_union_err_unkown_types(self, hge_ctx):
        """add a remote schema with a union having unknown types as memberTypes"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_union_err_unknown_types.yaml')

    def test_add_remote_schema_with_union_err_subtype_iface(self, hge_ctx):
        """add a remote schema with a union having interface as a memberType"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_union_err_member_type_interface.yaml')

    def test_add_remote_schema_with_union_err_wrapped_type(self, hge_ctx):
        """add a remote schema with error in spec for union"""
        check_query_f(hge_ctx, self.dir + '/add_remote_schema_with_union_err_wrapped_type.yaml')

    def test_bulk_remove_add_remote_schema(self, hge_ctx):
        st_code, resp = hge_ctx.v1q_f(self.dir + '/basic_bulk_remove_add.yaml')
        assert st_code == 200, resp


class TestAddRemoteSchemaTbls:
    """ tests with adding a table in hasura """

    dir = 'queries/remote_schemas'

    @pytest.fixture(autouse=True)
    def transact(self, hge_ctx):
        st_code, resp = hge_ctx.v1q_f('queries/remote_schemas/tbls_setup.yaml')
        assert st_code == 200, resp
        yield
        st_code, resp = hge_ctx.v1q_f('queries/remote_schemas/tbls_teardown.yaml')
        assert st_code == 200, resp

    def test_add_schema(self, hge_ctx):
        """ check if the remote schema is added in the db """
        res = hge_ctx.sql('select * from hdb_catalog.remote_schemas')
        row = res.fetchone()
        assert row['name'] == "simple2-graphql"

    def test_add_schema_conflicts_with_tables(self, hge_ctx):
        """add remote schema which conflicts with hasura tables"""
        q = mk_add_remote_q('simple2', 'http://localhost:5000/hello-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 400
        assert resp['code'] == 'remote-schema-conflicts'

    def test_add_second_remote_schema(self, hge_ctx):
        """add 2 remote schemas with different node and types"""
        q = mk_add_remote_q('my remote2', 'http://localhost:5000/country-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        hge_ctx.v1q({"type": "remove_remote_schema", "args": {"name": "my remote2"}})
        assert st_code == 200, resp

    def test_remote_query(self, hge_ctx):
        check_query_f(hge_ctx, self.dir + '/simple2_query.yaml')

    def test_remote_mutation(self, hge_ctx):
        check_query_f(hge_ctx, self.dir + '/simple2_mutation.yaml')

    def test_add_conflicting_table(self, hge_ctx):
        st_code, resp = hge_ctx.v1q_f(self.dir + '/create_conflicting_table.yaml')
        assert st_code == 400
        assert resp['code'] == 'remote-schema-conflicts'

    def test_introspection(self, hge_ctx):
        with open('queries/graphql_introspection/introspection.yaml') as f:
            query = yaml.load(f)
        st_code, resp = check_query(hge_ctx, query)
        assert st_code == 200, resp
        assert check_introspection_result(resp, ['User', 'hello'], ['user', 'hello'])

    def test_add_schema_duplicate_name(self, hge_ctx):
        q = mk_add_remote_q('simple2-graphql', 'http://localhost:5000/country-graphql')
        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 500, resp
        assert resp['code'] == 'postgres-error'

    def test_add_schema_same_type_containing_same_scalar(self, hge_ctx):
        """
        test types get merged when remote schema has type with same name and
        same structure + a same custom scalar
        """
        st_code, resp = hge_ctx.v1q_f(self.dir + '/person_table.yaml')
        assert st_code == 200, resp
        q = mk_add_remote_q('person-graphql', 'http://localhost:5000/person-graphql')

        st_code, resp = hge_ctx.v1q(q)
        assert st_code == 200, resp
        st_code, resp = hge_ctx.v1q_f(self.dir + '/drop_person_table.yaml')
        assert st_code == 200, resp
        hge_ctx.v1q({"type": "remove_remote_schema", "args": {"name": "person-graphql"}})
        assert st_code == 200, resp


class TestRemoteSchemaQueriesOverWebsocket:
    dir = 'queries/remote_schemas'
    teardown = {"type": "clear_metadata", "args": {}}

    @pytest.fixture(autouse=True)
    def transact(self, hge_ctx):
        st_code, resp = hge_ctx.v1q_f('queries/remote_schemas/tbls_setup.yaml')
        assert st_code == 200, resp
        yield
        # teardown
        st_code, resp = hge_ctx.v1q_f('queries/remote_schemas/tbls_teardown.yaml')
        assert st_code == 200, resp
        st_code, resp = hge_ctx.v1q(self.teardown)
        assert st_code == 200, resp

    def _init(self, hge_ctx):
        payload = {'type': 'connection_init', 'payload': {}}
        if hge_ctx.hge_key:
            payload['payload']['headers'] = {
                'x-hasura-admin-secret': hge_ctx.hge_key
            }
        hge_ctx.ws.send(json.dumps(payload))
        ev = hge_ctx.get_ws_event(3)
        assert ev['type'] == 'connection_ack', ev

    def _stop(self, hge_ctx, _id):
        data = {'id': _id, 'type': 'stop'}
        hge_ctx.ws.send(json.dumps(data))
        ev = hge_ctx.get_ws_event(3)
        assert ev['type'] == 'complete', ev

    def _send_query(self, hge_ctx, query):
        self._init(hge_ctx)
        _id = gen_id()
        frame = {
            'id': _id,
            'type': 'start',
            'payload': {'query': query},
        }
        if hge_ctx.hge_key:
            frame['payload']['headers'] = {
                'x-hasura-admin-secret': hge_ctx.hge_key
            }
        hge_ctx.ws.send(json.dumps(frame))
        return _id

    def test_remote_query(self, hge_ctx):
        self._init(hge_ctx)
        query = """
        query {
          user(id: 2) {
            id
            username
          }
        }
        """
        _id = self._send_query(hge_ctx, query)
        ev = hge_ctx.get_ws_event(3)
        assert ev['type'] == 'data' and ev['id'] == _id, ev
        assert ev['payload']['data']['data']['user']['username'] == 'john'
        self._stop(hge_ctx, _id)

    def test_remote_mutation(self, hge_ctx):
        self._init(hge_ctx)
        query = """
        mutation {
          createUser(id: 42, username: "foobar") {
            user {
              id
              username
            }
          }
        }
        """
        _id = self._send_query(hge_ctx, query)
        ev = hge_ctx.get_ws_event(3)
        assert ev['type'] == 'data' and ev['id'] == _id, ev
        assert ev['payload']['data']['data']['createUser']['user']['id'] == 42
        assert ev['payload']['data']['data']['createUser']['user']['username'] == 'foobar'
        self._stop(hge_ctx, _id)


class TestAddRemoteSchemaCompareRootQueryFields:

    remote = 'http://localhost:5000/default-value-echo-graphql'

    @pytest.fixture(autouse=True)
    def transact(self, hge_ctx):
        st_code, resp = hge_ctx.v1q(mk_add_remote_q('default_value_test', self.remote))
        assert st_code == 200, resp
        yield
        st_code, resp = hge_ctx.v1q(mk_delete_remote_q('default_value_test'))
        assert st_code == 200, resp

    def test_schema_check_arg_default_values_and_field_and_arg_types(self, hge_ctx):
        with open('queries/graphql_introspection/introspection.yaml') as f:
            query = yaml.load(f)
        st_code, introspect_hasura = check_query(hge_ctx, query)
        assert st_code == 200, introspect_hasura
        resp = requests.post(
            self.remote,
            json=query['query']
        )
        introspect_remote = resp.json()
        assert resp.status_code == 200, introspect_remote
        remote_root_ty_info = get_query_root_info(introspect_remote)
        hasura_root_ty_info = get_query_root_info(introspect_hasura)
        has_fld = dict()
        for fr in remote_root_ty_info['fields']:
            has_fld[fr['name']] = False
            for fh in filter(lambda f: f['name'] == fr['name'], hasura_root_ty_info['fields']):
                has_fld[fr['name']] = True
                assert fr['type'] == fh['type'], yaml.dump({
                    'error' : 'Types do not match for fld ' + fr['name'],
                    'remote_type' : fr['type'],
                    'hasura_type' : fh['type']
                })
                has_arg = dict()
                for ar in fr['args']:
                    arg_path = fr['name'] + '(' + ar['name'] + ':)'
                    has_arg[arg_path] = False
                    for ah in filter(lambda a: a['name'] == ar['name'], fh['args']):
                        has_arg[arg_path] = True
                        assert ar['type'] == ah['type'], yaml.dump({
                            'error' : 'Types do not match for arg ' + arg_path,
                            'remote_type' : ar['type'],
                            'hasura_type' : ah['type']
                        })
                        assert ar['defaultValue'] == ah['defaultValue'], yaml.dump({
                            'error' : 'Default values do not match for arg ' + arg_path,
                            'remote_default_value' : ar['defaultValue'],
                            'hasura_default_value' : ah['defaultValue']
                        })
                    assert has_arg[arg_path], 'Argument ' + arg_path + ' in the remote schema root query type not found in Hasura schema'
            assert has_fld[fr['name']], 'Field ' + fr['name'] + ' in the remote shema root query type not found in Hasura schema'


#    def test_remote_query_variables(self, hge_ctx):
#        pass
#    def test_add_schema_url_from_env(self, hge_ctx):
#        pass
#    def test_add_schema_header_from_env(self, hge_ctx):
#        pass


def _map(f, l):
    return list(map(f, l))

def _filter(f, l):
    return list(filter(f, l))

def get_query_root_info(res):
    root_ty_name = res['data']['__schema']['queryType']['name']
    return _filter(lambda ty: ty['name'] == root_ty_name, get_types(res))[0]

def get_types(res):
    return res['data']['__schema']['types']

def check_introspection_result(res, types, node_names):
    all_types = _map(lambda t: t['name'], res['data']['__schema']['types'])
    print(all_types)
    q_root = _filter(lambda t: t['name'] == 'query_root',
                     res['data']['__schema']['types'])[0]
    all_nodes = _map(lambda f: f['name'], q_root['fields'])
    print(all_nodes)

    satisfy_ty = True
    satisfy_node = True

    for ty_name in types:
        if ty_name not in all_types:
            satisfy_ty = False

    for nn in node_names:
        if nn not in all_nodes:
            satisfy_node = False

    return satisfy_node and satisfy_ty

def gen_id(size=6, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))
