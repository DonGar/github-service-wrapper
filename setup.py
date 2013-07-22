#!/usr/bin/python

import argparse
import os
import subprocess

class UnsafeName(Exception):
  pass

class UnsafeInstallDirectory(Exception):
  pass

class UnsafeCmd(Exception):
  pass

TEMPLATE = """
### BEGIN INIT INFO
# Provides: GPIO Polling with web reporting
# Required-Start: $remote_fs $syslog
# Required-Stop: $remote_fs $syslog
# Default-Start: 2 3 4 5
# Default-Stop: 0 1 6
# Short-Description: GPIO Polling
# Description: GPIO Polling with reporting to house-monitor
### END INIT INFO

#! /bin/sh
# /etc/init.d/PROJECT_NAME

# This init script created by:
#   https://github.com/DonGar/github-service-wrapper.git

DAEMON_PATH="PROJECT_PATH"
DAEMON="PROJECT_CMD"

NAME="PROJECT_NAME"
DESC="My daemon description"
PIDFILE=/var/run/$NAME.pid
SCRIPTNAME=/etc/init.d/$NAME

case "$1" in
start)
    printf "%-50s" "Starting $NAME..."
    cd $DAEMON_PATH
    git pull
    PID=`./$DAEMON > /dev/null 2>&1 & echo $!`
    if [ -z $PID ]; then
        printf "%s\n" "Fail"
    else
        echo $PID > $PIDFILE
        printf "%s\n" "Ok"
    fi
;;
status)
    printf "%-50s" "Checking $NAME..."
    if [ -f $PIDFILE ]; then
        PID=`cat $PIDFILE`
        if [ -z "`ps axf | grep ${PID} | grep -v grep`" ]; then
            printf "%s\n" "Process dead but pidfile exists"
        else
            echo "Running"
        fi
    else
        printf "%s\n" "Service not running"
    fi
;;
stop)
    printf "%-50s" "Stopping $NAME"
    PID=`cat $PIDFILE`
    cd $DAEMON_PATH
    if [ -f $PIDFILE ]; then
        kill -HUP $PID
        printf "%s\n" "Ok"
        rm -f $PIDFILE
    else
        printf "%s\n" "pidfile not found"
    fi
;;

restart)
    $0 stop
    $0 start
;;

*)
    echo "Usage: $0 {status|start|stop|restart}"
    exit 1
esac
"""

def parse_args():
  parser = argparse.ArgumentParser(
      description='Install new init script for github project.')

  parser.add_argument('--name')
  parser.add_argument('--path')
  parser.add_argument('url')
  parser.add_argument('cmd')
  parser.add_argument('cmd_args', nargs=argparse.REMAINDER)

  args = parser.parse_args()

  # Discover the default name if there isn't an explicit one.
  if args.name is None:
    # 'https://github.com/DonGar/github-service-wrapper.git' >
    #    'github-service-wrapper.git' ->
    #    ('github-service-wrapper', '.git') ->
    #    'github-service-wrapper'
    args.name = os.path.splitext(os.path.basename(args.url))[0]

  if args.path is None:
    args.path = os.path.join('/usr/local', args.name)

  # Turn the install path into an absolute path.
  args.path = os.path.abspath(args.path)

  args.cmd = [args.cmd] + args.cmd_args

  return args


def sanity_check(init_script_name, name, path):

  # name should be a simple name with no path elements.
  if os.path.dirname(name) != '':
    raise UnsafeName('Name should be simple: %s' % name)

  # If the init script already exists, ensure we created it previously.
  if os.path.exists(init_script_name):
    with open(init_script_name, 'r') as init_script:
      contents = init_script.read()

      # If doesn't contain this string, we didn't creat it.
      if contents.find('github-service-wrapper') == -1:
        raise UnsafeName('Trying to replace existing %s.' % init_script_name)


def clone_repo(url, path):

  # If the git clone target dir exists, or is empty, do a clone.
  if not os.path.exists(path) or not os.listdir(path):
    subprocess.check_call(['git', 'clone', url, path])
    return

  # If the dir eixsts and is not a git repo, don't use it. It's dangerous.
  if not os.path.exists(os.path.join(path, '.git')):
    raise UnsafeInstallDirectory('Install dir is not empty: %s' % path)

  # If the dir exists, and is a git repo, see if it points to our URL.
  old_url = subprocess.check_output(['git', 'config', 'remote.origin.url'],
                                    cwd=path)
  old_url = old_url.strip()

  if url != old_url:
    raise UnsafeInstallDirectory('Install dir contains a checkout from: %s' %
                                 old_url)

  subprocess.check_call(['git', 'pull'], cwd=path)


def install_init_d(init_script_name, name, path, cmd):

  # Create the init script by filling in values in TEMPLATE.
  template = TEMPLATE
  template = template.replace('PROJECT_NAME', name)
  template = template.replace('PROJECT_PATH', path)
  template = template.replace('PROJECT_CMD', ' '.join(cmd))

  # Write out the template.
  with open(init_script_name, 'w+') as init_script:
    init_script.write(template)

  # Make it executable.
  os.chmod(init_script_name, 0755)


def sanity_check_cmd(path, cmd):
  cmd_name = os.path.join(path, cmd[0])

  if not os.path.isfile(cmd_name) or not os.access(cmd_name, os.X_OK):
    raise UnsafeCmd('Command not present in checkout: "%s"' % cmd_name)


def main():
  args = parse_args()

  init_script_name = os.path.join('/etc/init.d/', args.name)

  print 'Setting up:     %s' % args.name
  print '  Cloning from:   %s' % args.url
  print '  Into:           %s' % args.path
  print '  Script:         %s' % init_script_name
  print '  Daemon:         %s' % ' '.join(args.cmd)

  # Sanity check args
  sanity_check(init_script_name, args.name, args.path)

  # Setup the new repo.
  clone_repo(args.url, args.path)

  # Verify that the command exists in the repo.
  sanity_check_cmd(args.path, args.cmd)

  # Setup the init script, and set it to run.
  install_init_d(init_script_name, args.name, args.path, args.cmd)
  #subprocess.check_call(['update-rc.d', args.name, 'defaults'])


if __name__ == "__main__":
    main()
