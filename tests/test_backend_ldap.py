# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
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

import ldap
import uuid
import nose.exc

from keystone.common import ldap as ldap_common
from keystone.common.ldap import fakeldap
from keystone import config
from keystone import exception
from keystone import identity
from keystone import test

import default_fixtures
import test_backend


CONF = config.CONF


def clear_database():
    db = fakeldap.FakeShelve().get_instance()
    db.clear()


class LDAPIdentity(test.TestCase, test_backend.IdentityTests):
    def setUp(self):
        super(LDAPIdentity, self).setUp()
        self.config([test.etcdir('keystone.conf.sample'),
                     test.testsdir('test_overrides.conf'),
                     test.testsdir('backend_ldap.conf')])
        clear_database()
        self.identity_man = identity.Manager()
        self.identity_api = self.identity_man.driver
        self.load_fixtures(default_fixtures)

    def test_build_tree(self):
        """Regression test for building the tree names
        """
        user_api = identity.backends.ldap.UserApi(CONF)
        self.assertTrue(user_api)
        self.assertEquals(user_api.tree_dn, "ou=Users,%s" % CONF.ldap.suffix)

    def test_configurable_allowed_user_actions(self):
        self.identity_api = identity.backends.ldap.Identity()

        user = {'id': 'fake1',
                'name': 'fake1',
                'password': 'fakepass1',
                'tenants': ['bar']}
        self.identity_man.create_user({}, 'fake1', user)
        user_ref = self.identity_api.get_user('fake1')
        self.assertEqual(user_ref['id'], 'fake1')

        user['password'] = 'fakepass2'
        self.identity_api.update_user('fake1', user)

        self.identity_api.delete_user('fake1')
        self.assertRaises(exception.UserNotFound,
                          self.identity_api.get_user,
                          'fake1')

    def test_configurable_forbidden_user_actions(self):
        CONF.ldap.user_allow_create = False
        CONF.ldap.user_allow_update = False
        CONF.ldap.user_allow_delete = False
        self.identity_api = identity.backends.ldap.Identity()

        user = {'id': 'fake1',
                'name': 'fake1',
                'password': 'fakepass1',
                'tenants': ['bar']}
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.create_user,
                          'fake1',
                          user)

        self.user_foo['password'] = 'fakepass2'
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.update_user,
                          self.user_foo['id'],
                          self.user_foo)

        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.delete_user,
                          self.user_foo['id'])

    def test_configurable_allowed_project_actions(self):
        self.identity_api = identity.backends.ldap.Identity()

        tenant = {'id': 'fake1', 'name': 'fake1', 'enabled': True}
        self.identity_man.create_project({}, 'fake1', tenant)
        tenant_ref = self.identity_api.get_project('fake1')
        self.assertEqual(tenant_ref['id'], 'fake1')

        tenant['enabled'] = 'False'
        self.identity_api.update_project('fake1', tenant)

        self.identity_api.delete_project('fake1')
        self.assertRaises(exception.ProjectNotFound,
                          self.identity_api.get_project,
                          'fake1')

    def test_configurable_forbidden_project_actions(self):
        CONF.ldap.tenant_allow_create = False
        CONF.ldap.tenant_allow_update = False
        CONF.ldap.tenant_allow_delete = False
        self.identity_api = identity.backends.ldap.Identity()

        tenant = {'id': 'fake1', 'name': 'fake1'}
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.create_project,
                          'fake1',
                          tenant)

        self.tenant_bar['enabled'] = 'False'
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.update_project,
                          self.tenant_bar['id'],
                          self.tenant_bar)
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.delete_project,
                          self.tenant_bar['id'])

    def test_configurable_allowed_role_actions(self):
        self.identity_api = identity.backends.ldap.Identity()

        role = {'id': 'fake1', 'name': 'fake1'}
        self.identity_api.create_role('fake1', role)
        role_ref = self.identity_api.get_role('fake1')
        self.assertEqual(role_ref['id'], 'fake1')

        role['name'] = 'fake2'
        self.identity_api.update_role('fake1', role)

        self.identity_api.delete_role('fake1')
        self.assertRaises(exception.RoleNotFound,
                          self.identity_api.get_role,
                          'fake1')

    def test_configurable_forbidden_role_actions(self):
        CONF.ldap.role_allow_create = False
        CONF.ldap.role_allow_update = False
        CONF.ldap.role_allow_delete = False
        self.identity_api = identity.backends.ldap.Identity()

        role = {'id': uuid.uuid4().hex, 'name': uuid.uuid4().hex}
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.create_role,
                          role['id'],
                          role)

        self.role_member['name'] = uuid.uuid4().hex
        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.update_role,
                          self.role_member['id'],
                          self.role_member)

        self.assertRaises(exception.ForbiddenAction,
                          self.identity_api.delete_role,
                          self.role_member['id'])

    def test_user_filter(self):
        user_ref = self.identity_api.get_user(self.user_foo['id'])
        self.user_foo.pop('password')
        self.assertDictEqual(user_ref, self.user_foo)

        CONF.ldap.user_filter = '(CN=DOES_NOT_MATCH)'
        self.identity_api = identity.backends.ldap.Identity()
        self.assertRaises(exception.UserNotFound,
                          self.identity_api.get_user,
                          self.user_foo['id'])

    def test_project_filter(self):
        tenant_ref = self.identity_api.get_project(self.tenant_bar['id'])
        self.assertDictEqual(tenant_ref, self.tenant_bar)

        CONF.ldap.tenant_filter = '(CN=DOES_NOT_MATCH)'
        self.identity_api = identity.backends.ldap.Identity()
        self.assertRaises(exception.ProjectNotFound,
                          self.identity_api.get_project,
                          self.tenant_bar['id'])

    def test_role_filter(self):
        role_ref = self.identity_api.get_role(self.role_member['id'])
        self.assertDictEqual(role_ref, self.role_member)

        CONF.ldap.role_filter = '(CN=DOES_NOT_MATCH)'
        self.identity_api = identity.backends.ldap.Identity()
        self.assertRaises(exception.RoleNotFound,
                          self.identity_api.get_role,
                          self.role_member['id'])

    def test_dumb_member(self):
        CONF.ldap.use_dumb_member = True
        CONF.ldap.dumb_member = 'cn=dumb,cn=example,cn=com'
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        self.assertRaises(exception.UserNotFound,
                          self.identity_api.get_user,
                          'dumb')

    def test_user_attribute_mapping(self):
        CONF.ldap.user_name_attribute = 'sn'
        CONF.ldap.user_mail_attribute = 'email'
        CONF.ldap.user_enabled_attribute = 'enabled'
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        user_ref = self.identity_api.get_user(self.user_two['id'])
        self.assertEqual(user_ref['id'], self.user_two['id'])
        self.assertEqual(user_ref['name'], self.user_two['name'])
        self.assertEqual(user_ref['email'], self.user_two['email'])
        self.assertEqual(user_ref['enabled'], self.user_two['enabled'])

        CONF.ldap.user_name_attribute = 'email'
        CONF.ldap.user_mail_attribute = 'sn'
        self.identity_api = identity.backends.ldap.Identity()
        user_ref = self.identity_api.get_user(self.user_two['id'])
        self.assertEqual(user_ref['id'], self.user_two['id'])
        self.assertEqual(user_ref['name'], self.user_two['email'])
        self.assertEqual(user_ref['email'], self.user_two['name'])
        self.assertEqual(user_ref['enabled'], self.user_two['enabled'])

    def test_user_attribute_ignore(self):
        CONF.ldap.user_attribute_ignore = ['name', 'email', 'password',
                                           'tenant_id', 'enabled', 'tenants']
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        user_ref = self.identity_api.get_user(self.user_two['id'])
        self.assertEqual(user_ref['id'], self.user_two['id'])
        self.assertNotIn('name', user_ref)
        self.assertNotIn('email', user_ref)
        self.assertNotIn('password', user_ref)
        self.assertNotIn('tenant_id', user_ref)
        self.assertNotIn('enabled', user_ref)
        self.assertNotIn('tenants', user_ref)

    def test_project_attribute_mapping(self):
        CONF.ldap.tenant_name_attribute = 'ou'
        CONF.ldap.tenant_desc_attribute = 'desc'
        CONF.ldap.tenant_enabled_attribute = 'enabled'
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        tenant_ref = self.identity_api.get_project(self.tenant_baz['id'])
        self.assertEqual(tenant_ref['id'], self.tenant_baz['id'])
        self.assertEqual(tenant_ref['name'], self.tenant_baz['name'])
        self.assertEqual(
            tenant_ref['description'],
            self.tenant_baz['description'])
        self.assertEqual(tenant_ref['enabled'], self.tenant_baz['enabled'])

        CONF.ldap.tenant_name_attribute = 'desc'
        CONF.ldap.tenant_desc_attribute = 'ou'
        self.identity_api = identity.backends.ldap.Identity()
        tenant_ref = self.identity_api.get_project(self.tenant_baz['id'])
        self.assertEqual(tenant_ref['id'], self.tenant_baz['id'])
        self.assertEqual(tenant_ref['name'], self.tenant_baz['description'])
        self.assertEqual(tenant_ref['description'], self.tenant_baz['name'])
        self.assertEqual(tenant_ref['enabled'], self.tenant_baz['enabled'])

    def test_project_attribute_ignore(self):
        CONF.ldap.tenant_attribute_ignore = ['name',
                                             'description',
                                             'enabled']
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        tenant_ref = self.identity_api.get_project(self.tenant_baz['id'])
        self.assertEqual(tenant_ref['id'], self.tenant_baz['id'])
        self.assertNotIn('name', tenant_ref)
        self.assertNotIn('description', tenant_ref)
        self.assertNotIn('enabled', tenant_ref)

    def test_role_attribute_mapping(self):
        CONF.ldap.role_name_attribute = 'ou'
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        role_ref = self.identity_api.get_role(self.role_member['id'])
        self.assertEqual(role_ref['id'], self.role_member['id'])
        self.assertEqual(role_ref['name'], self.role_member['name'])

        CONF.ldap.role_name_attribute = 'sn'
        self.identity_api = identity.backends.ldap.Identity()
        role_ref = self.identity_api.get_role(self.role_member['id'])
        self.assertEqual(role_ref['id'], self.role_member['id'])
        self.assertNotIn('name', role_ref)

    def test_role_attribute_ignore(self):
        CONF.ldap.role_attribute_ignore = ['name']
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        self.load_fixtures(default_fixtures)
        role_ref = self.identity_api.get_role(self.role_member['id'])
        self.assertEqual(role_ref['id'], self.role_member['id'])
        self.assertNotIn('name', role_ref)

    def test_user_enable_attribute_mask(self):
        CONF.ldap.user_enabled_attribute = 'enabled'
        CONF.ldap.user_enabled_mask = 2
        CONF.ldap.user_enabled_default = 512
        clear_database()
        self.identity_api = identity.backends.ldap.Identity()
        user = {'id': 'fake1', 'name': 'fake1', 'enabled': True}
        self.identity_man.create_user({}, 'fake1', user)
        user_ref = self.identity_api.get_user('fake1')
        self.assertEqual(user_ref['enabled'], True)

        user['enabled'] = False
        self.identity_api.update_user('fake1', user)
        user_ref = self.identity_api.get_user('fake1')
        self.assertEqual(user_ref['enabled'], False)

        user['enabled'] = True
        self.identity_api.update_user('fake1', user)
        user_ref = self.identity_api.get_user('fake1')
        self.assertEqual(user_ref['enabled'], True)

    def test_user_api_get_connection_no_user_password(self):
        """Don't bind in case the user and password are blank"""
        self.config([test.etcdir('keystone.conf.sample'),
                     test.testsdir('test_overrides.conf')])
        CONF.ldap.url = "fake://memory"
        user_api = identity.backends.ldap.UserApi(CONF)
        self.stubs.Set(fakeldap, 'FakeLdap',
                       self.mox.CreateMock(fakeldap.FakeLdap))
        # we have to track all calls on 'conn' to make sure that
        # conn.simple_bind_s is not called
        conn = self.mox.CreateMockAnything()
        conn = fakeldap.FakeLdap(CONF.ldap.url).AndReturn(conn)
        self.mox.ReplayAll()

        user_api.get_connection(user=None, password=None)

    def test_wrong_ldap_scope(self):
        CONF.ldap.query_scope = uuid.uuid4().hex
        self.assertRaisesRegexp(
            ValueError,
            'Invalid LDAP scope: %s. *' % CONF.ldap.query_scope,
            identity.backends.ldap.Identity)

# TODO (henry-nash) These need to be removed when the full LDAP implementation
# is submitted - see Bugs 1092187, 1101287, 1101276, 1101289
    def test_group_crud(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_add_user_to_group(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_add_user_to_group_404(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_check_user_in_group(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_check_user_not_in_group(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_list_users_in_group(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_remove_user_from_group(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_remove_user_from_group_404(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_get_role_grant_by_user_and_project(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_role_grants_for_user_and_project_404(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_add_role_grant_to_user_and_project_404(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_remove_role_grant_from_user_and_project(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_and_remove_role_grant_by_group_and_project(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_and_remove_role_grant_by_group_and_domain(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_and_remove_role_grant_by_user_and_domain(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_and_remove_correct_role_grant_from_a_mix(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_domain_crud(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_project_crud(self):
        raise nose.exc.SkipTest('Blocked by bug 1101289')

    def test_get_and_remove_role_grant_by_group_and_cross_domain(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_and_remove_role_grant_by_user_and_cross_domain(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_role_grant_by_group_and_cross_domain_project(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_role_grant_by_user_and_cross_domain_project(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_multi_role_grant_by_user_group_on_project_domain(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_delete_role_with_user_and_group_grants(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_delete_user_with_group_project_domain_links(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_delete_group_with_user_project_domain_links(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_list_groups(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_list_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_list_user_projects(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_get_project_users(self):
        raise nose.exc.SkipTest('Blocked by bug 1101287')

    def test_create_duplicate_user_name_in_different_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_create_duplicate_project_name_in_different_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_create_duplicate_group_name_fails(self):
        raise nose.exc.SkipTest('Blocked by bug 1092187')

    def test_create_duplicate_group_name_in_different_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_user_between_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_user_between_domains_with_clashing_names_fails(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_group_between_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_group_between_domains_with_clashing_names_fails(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_project_between_domains(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')

    def test_move_project_between_domains_with_clashing_names_fails(self):
        raise nose.exc.SkipTest('Blocked by bug 1101276')


class LDAPIdentityEnabledEmulation(LDAPIdentity):
    def setUp(self):
        super(LDAPIdentityEnabledEmulation, self).setUp()
        self.config([test.etcdir('keystone.conf.sample'),
                     test.testsdir('test_overrides.conf'),
                     test.testsdir('backend_ldap.conf')])
        CONF.ldap.user_enabled_emulation = True
        CONF.ldap.tenant_enabled_emulation = True
        clear_database()
        self.identity_man = identity.Manager()
        self.identity_api = self.identity_man.driver
        self.load_fixtures(default_fixtures)
        for obj in [self.tenant_bar, self.tenant_baz, self.user_foo,
                    self.user_two, self.user_badguy]:
            obj.setdefault('enabled', True)

    def test_authenticate_no_metadata(self):
        user = {
            'id': 'no_meta',
            'name': 'NO_META',
            'domain_id': test_backend.DEFAULT_DOMAIN_ID,
            'password': 'no_meta2',
            'enabled': True,
        }
        self.identity_man.create_user({}, user['id'], user)
        self.identity_api.add_user_to_project(self.tenant_baz['id'],
                                              user['id'])
        user_ref, tenant_ref, metadata_ref = self.identity_api.authenticate(
            user_id=user['id'],
            tenant_id=self.tenant_baz['id'],
            password=user['password'])
        # NOTE(termie): the password field is left in user_foo to make
        #               it easier to authenticate in tests, but should
        #               not be returned by the api
        user.pop('password')
        self.assertEquals(metadata_ref, {"roles":
                                         [CONF.member_role_id]})
        self.assertDictEqual(user_ref, user)
        self.assertDictEqual(tenant_ref, self.tenant_baz)

    def test_user_crud(self):
        user = {'domain_id': uuid.uuid4().hex, 'id': uuid.uuid4().hex,
                'name': uuid.uuid4().hex, 'password': 'passw0rd'}
        self.identity_man.create_user({}, user['id'], user)
        user['enabled'] = True
        user_ref = self.identity_api.get_user(user['id'])
        del user['password']
        user_ref_dict = dict((x, user_ref[x]) for x in user_ref)
        self.assertDictEqual(user_ref_dict, user)

        user['password'] = uuid.uuid4().hex
        self.identity_api.update_user(user['id'], user)
        user_ref = self.identity_api.get_user(user['id'])
        del user['password']
        user_ref_dict = dict((x, user_ref[x]) for x in user_ref)
        self.assertDictEqual(user_ref_dict, user)

        self.identity_api.delete_user(user['id'])
        self.assertRaises(exception.UserNotFound,
                          self.identity_api.get_user,
                          user['id'])

    def test_user_enable_attribute_mask(self):
        raise nose.exc.SkipTest(
            "Enabled emulation conflicts with enabled mask")
