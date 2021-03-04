#!/usr/bin/env python

# Copyright (C) 2014 Bloomberg L.P. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This script implements the bare bones "gclient runhooks" behavior so that we
# don't need to have gclient installed everywhere.  Also, arguments passed to
# this script will be forwarded to gyp.

import os, sys, subprocess, gclient_eval
import vs_toolchain, shutil

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

_SRC_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, os.path.pardir))

# Absolute path to the directory that stores pgo related state files, which
# specifcies which profile to update and use.
_PGO_DIR = os.path.join(_SRC_ROOT, 'chrome', 'build')

# Absolute path to the directory that stores pgo profiles.
_PGO_PROFILE_DIR = os.path.join(_PGO_DIR, 'pgo_profiles')

# Configurations
_checkout_pgo_profiles = True

def execInShell(cmd):
  print "Executing '" + " ".join(cmd) + "'"
  sys.stdout.flush()
  return subprocess.call(cmd, shell=True)


def dummyVar(s):
  return s

def config(s):
  if s == 'checkout_pgo_profiles':
    return _checkout_pgo_profiles
  else:
    raise Exception("Invalid config name %s" % s)

def loadDepInfo(solution):
  name = solution['name']
  deps = solution['deps_file']
  scope = {
    'Var': dummyVar,
    'Str': gclient_eval.ConstantString,
    'Config': config
  }
  execfile(os.path.join(name, deps), scope)
  return {
      'hooks': scope['hooks'],
      'vars': scope['vars']
  }

def get_vars(dep_vars):
  """Returns a dictionary of effective variable values
  (DEPS file contents with applied custom_vars overrides)."""
  # Provide some built-in variables.
  result = {
      'checkout_android': False,
      'checkout_chromeos': False,
      'checkout_fuchsia': False,
      'checkout_ios': False,
      'checkout_linux': False,
      'checkout_mac': False,
      'checkout_win': True,
      'host_os': "win",

      'checkout_arm': False,
      'checkout_arm64': False,
      'checkout_x86': True,
      'checkout_mips': False,
      'checkout_mips64': False,
      'checkout_ppc': False,
      'checkout_s390': False,
      'checkout_x64': True,
  }

  # Variable precedence:
  # - built-in
  # - DEPS vars
  result.update(dep_vars)
  return result


# function copied from update_pgo_profiles.py
def _read_profile_name(target):
  """Read profile name given a target.

  Args:
    target(str): The target name, such as win32, mac.

  Returns:
    Name of the profile to update and use, such as:
    chrome-win32-master-67ad3c89d2017131cc9ce664a1580315517550d1.profdata.
  """
  state_file = os.path.join(_PGO_DIR, '%s.pgo.txt' % target)
  with open(state_file, 'r') as f:
    profile_name = f.read().strip()

  return profile_name

def main(args):
  global _checkout_pgo_profiles
  toolchainDir = None

  useToolchainDevkit = bool(int(os.environ.get('DEPOT_TOOLS_WIN_TOOLCHAIN', '1')))
  if useToolchainDevkit:
    base_url = os.environ.get('DEPOT_TOOLS_WIN_TOOLCHAIN_BASE_URL', '')
    toolchainDir = os.path.join(base_url, vs_toolchain.DEVKIT_VERSION)

  # Need to be in the root directory
  os.chdir(os.path.join(_SCRIPT_DIR, os.pardir, os.pardir))

  # Copy PGO profiles
  if toolchainDir:
    _checkout_pgo_profiles = False

    if not os.path.exists(_PGO_PROFILE_DIR):
      os.mkdir(_PGO_PROFILE_DIR)

    for target in ['win32', 'win64']:
      print("Copying PGO profile for %s" % target)
      profile_name = _read_profile_name(target)
      dest_path = os.path.join(_PGO_PROFILE_DIR, profile_name)
      src_path = os.path.join(toolchainDir, 'pgo_profiles', profile_name)
      shutil.copyfile(src_path, dest_path)

  else:
    _checkout_pgo_profiles = True

  scope = {}
  execfile('.gclient', scope)
  for sln in scope['solutions']:
    dep_info = loadDepInfo(sln)
    hooks = dep_info['hooks']

    for hook in hooks:
      cond = hook.get('condition', 'True')
      if not gclient_eval.EvaluateCondition(cond, get_vars(dep_info['vars'])):
        continue

      cmd = hook['action']
      if hook['name'] == 'gyp':
        cmd.extend(args)
      rc = execInShell(cmd)
      if 0 != rc:
        return rc

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))

