#!/usr/bin/python
#coding: utf-8 -*-
# (c) 2014, David Lundgren <dlundgren@syberisle.net>
#
# This file is part of Ansible
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the MIT license.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# MIT License for more details.
#
# You should have received a copy of the MIT.
# If not, see <http://opensource.org/licenses/MIT>.

DOCUMENTATION = '''
---
module: sysrc
short_description: Manage FreeBSD /etc/rc.conf
requirements: []
version_added: 1.7
author: David Lundgren
description:
    - Manages the /etc/rc.conf for FreeBSD
options:
    name:
        required: true
        description:
            - Name of variable in $dest to manage.
            - NOTE: cannot use . (periods) in the name as sysrc doesn't support it
    value:
        required: false
        description:
            - The value if "present"
    state:
        required: false
        default: "present"
        choices: [ present, absent, append, subtract ]
        description:
            - Whether the var should be present or absent in $dest.
            - append/subtract will add or remove the value from a list.
    dest:
        required: false
        default: "/etc/rc.conf"
        description:
            - What file should be operated on
    delim:
        required: false
        default: " "
        description:
            - Delimiter used in append/subtract mode
    jail:
        required: false
        description:
            - Name or ID of the jail to operate on
'''

EXAMPLES = '''
---
# enable mysql in the /etc/rc.conf
- name: Configure mysql pid file
  sysrc:
    name: mysql_pidfile
    value: "/var/run/mysqld/mysqld.pid"

# enable accf_http kld in the boot loader
- name: enable accf_http kld
  sysrc:
    name: accf_http_load
    state: present
    value: "YES"
    dest: /boot/loader.conf

# add gif0 to cloned_interfaces
- name: add gif0 interface
  sysrc:
    name: cloned_interfaces
    state: append
    value: "gif0"

# enable nginx on a jail
- name: add gif0 interface
  sysrc:
    name: nginx_enable
    value: "YES"
    jail: www
'''

import re
from ansible.module_utils.basic import *

class sysrc(object):
    def __init__(self, module, name, value, dest, delim, jail):
        self.module  = module
        self.name    = name
        self.changed = False
        self.value   = value
        self.dest    = dest
        self.delim   = delim
        self.jail    = jail
        self.sysrc   = module.get_bin_path('sysrc', True)

    def exists(self):
        # sysrc doesn't really use exit codes
        (rc, out, err) = self.run_sysrc(self.name)
        if out.find("unknown variable") == -1 and re.match("%s: %s$" % (re.escape(self.name), re.escape(self.value)), out) is not None:
            return True
        else:
            return False

    def contains(self):
        (rc, out, err) = self.run_sysrc('-n', self.name)
        if out.find("unknown variable") == -1:
            values = out.strip().split(self.delim)
            if self.value in values:
                return True
            else:
                return False
        else:
            return False

    def create(self):
        if self.module.check_mode:
            self.changed = True
            return

        (rc, out, err) = self.run_sysrc("%s=%s" % (self.name, self.value))
        if out.find("%s:" % (self.name)) == 0 and re.search("\-\> %s$" % re.escape(self.value), out) is not None:
            self.changed = True
            return True
        else:
            return False

    def destroy(self):
        if self.module.check_mode:
            self.changed = True
            return

        (rc, out, err) = self.run_sysrc('-x', self.name)
        if out.find("unknown variable") == -1:
            return False
        else:
            self.changed = True
            return True

    def append(self):
        if self.module.check_mode:
            self.changed = True
            return

        setstring = '%s+=%s%s' % (self.name, self.delim, self.value)
        (rc, out, err) = self.run_sysrc(setstring)
        if out.find("%s:" % (self.name)) == 0:
            values = out.split(' -> ')[1].strip().split(self.delim)
            if self.value in values:
                self.changed = True
                return True
            else:
                return False
        else:
            return False

    def subtract(self):
        if self.module.check_mode:
            self.changed = True
            return

        setstring = '%s-=%s%s' % (self.name, self.delim, self.value)
        (rc, out, err) = self.run_sysrc(setstring)
        if out.find("%s:" % (self.name)) == 0:
            values = out.split(' -> ')[1].strip().split(self.delim)
            if self.value in values:
                return False
            else:
                self.changed = True
                return True
        else:
            return False

    def run_sysrc(self, *args):
        cmd = [self.sysrc, '-f', self.dest]
        if self.jail:
            cmd += ['-j', self.jail]
        cmd.extend(args)

        return self.module.run_command(cmd)


def main():
    module = AnsibleModule(
        argument_spec = dict(
            name  = dict(
                required = True
            ),
            value = dict(
                default = None
            ),
            state = dict(
                default = 'present',
                choices = [ 'present', 'absent', 'append', 'subtract' ]
            ),
            dest  = dict(
                default = '/etc/rc.conf'
            ),
            delim = dict(
                default = ' '
            ),
            jail = dict(
                default = None
            ),
        ),
        supports_check_mode=True,
    )

    name   = module.params.pop('name')
    value  = module.params.pop('value')
    state  = module.params.pop('state')
    dest   = module.params.pop('dest')
    delim  = module.params.pop('delim')
    jail   = module.params.pop('jail')
    result = {
        'name'  : name,
        'state' : state,
        'value' : value,
        'dest'  : dest,
        'delim' : delim,
        'jail'  : jail,
    }

    rcValue = sysrc(module, name, value, dest, delim, jail)

    if state == 'present':
        not rcValue.exists() and rcValue.create()
    elif state == 'absent':
        rcValue.exists() and rcValue.destroy()
    elif state == 'append':
        not rcValue.contains() and rcValue.append()
    elif state == 'subtract':
        rcValue.contains() and rcValue.subtract()

    result['changed'] = rcValue.changed

    module.exit_json(**result)

main()

