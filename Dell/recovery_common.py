#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# «recovery_common» - Misc Functions and variables that are useful in many areas
#
# Copyright (C) 2009, Dell Inc.
#
# Author:
#  - Mario Limonciello <Mario_Limonciello@Dell.com>
#
# This is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this application; if not, write to the Free Software Foundation, Inc., 51
# Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
##################################################################################

import dbus.mainloop.glib
import subprocess
import gobject
import os
import re

##                ##
##Common Variables##
##                ##

DBUS_BUS_NAME = 'com.dell.RecoveryMedia'
DBUS_INTERFACE_NAME = 'com.dell.RecoveryMedia'


#Translation Support
domain='dell-recovery'
LOCALEDIR='/usr/share/locale'

#UI file directory
if os.path.isdir('gtk') and 'DEBUG' in os.environ:
    UIDIR= 'gtk'
else:
    UIDIR = '/usr/share/dell'


#Supported burners and their arguments
dvd_burners = { 'brasero':['-i'],
               'nautilus-cd-burner':['--source-iso='] }
usb_burners = { 'usb-creator':['-n','--iso'],
                'usb-creator-gtk':['-n','--iso'],
                'usb-creator-kde':['-n','--iso'] }

if 'INTRANET' in os.environ:
    url="humbolt.us.dell.com/pub/linux.dell.com/srv/www/vhosts/linux.dell.com/html"
else:
    url="linux.dell.com"

git_trees = { 'ubuntu': 'http://' + url + '/git/ubuntu-fid.git',
              'redhat': 'http://humbolt.us.dell.com/pub/Applications/git-internal-projects/redhat-fid.git',
            }

##                ##
##Common Functions##
##                ##
def white_tree(action,whitelist,src,dst='',base=None):
    """Recursively ACTIONs files from src to dest only
       when they match the whitelist outlined in whitelist"""
    from distutils.file_util import copy_file
    from distutils.dir_util import mkpath

    if base is None:
        base=src
        if not base.endswith('/'):
            base += '/'

    names = os.listdir(src)

    if action == "copy":
        outputs = []
    elif action == "size":
        outputs = 0

    for n in names:
        src_name = os.path.join(src, n)
        dst_name = os.path.join(dst, n)
        end=src_name.split(base)[1]

        #don't copy symlinks or hardlinks, vfat seems to hate them
        if os.path.islink(src_name):
            continue

        #recurse till we find FILES
        elif os.path.isdir(src_name):
            if action == "copy":
                outputs.extend(
                    white_tree(action, whitelist, src_name, dst_name, base))
            elif action == "size":
                #add the directory we're in
                outputs += os.path.getsize(src_name)
                #add the files in that directory
                outputs += white_tree(action, whitelist, src_name, dst_name, base)

        #only copy the file if it matches the whitelist
        elif whitelist.search(end):
            if action == "copy":
                if not os.path.isdir(dst):
                    os.makedirs(dst)
                copy_file(src_name, dst_name, preserve_mode=1,
                          preserve_times=1, update=1, dry_run=0)
                outputs.append(dst_name)

            elif action == "size":
                outputs += os.path.getsize(src_name)

    return outputs

def check_vendor():
    if os.path.exists('/sys/class/dmi/id/bios_vendor'):
        with open('/sys/class/dmi/id/bios_vendor') as file:
            vendor = file.readline().strip('\n')
    else:
        vendor = ''
    return (vendor == 'dell' or vendor == 'innotek')

def find_partitions(up,rp):
    """Searches the system for utility and recovery partitions"""
    bus = dbus.SystemBus()

    try:
        #first try to use udisks, if this fails, fall back to devkit-disks.
        udisk_obj = bus.get_object('org.freedesktop.UDisks', '/org/freedesktop/UDisks')
        ud = dbus.Interface(udisk_obj, 'org.freedesktop.UDisks')
        devices = ud.EnumerateDevices()
        for device in devices:
            dev_obj = bus.get_object('org.freedesktop.UDisks', device)
            dev = dbus.Interface(dev_obj, 'org.freedesktop.DBus.Properties')

            label = dev.Get('org.freedesktop.UDisks.Device','IdLabel')
            fs = dev.Get('org.freedesktop.Udisks.Device','IdType')

            if not up and 'DellUtility' in label:
                up=dev.Get('org.freedesktop.UDisks.Device','DeviceFile')
            elif not rp and ('install' in label or 'OS' in label) and 'vfat' in fs:
                rp=dev.Get('org.freedesktop.Udisks.Device','DeviceFile')
        return (up,rp)
    except dbus.DBusException, e:
        print "%s, UDisks Failed" % str(e)

    try:
        #next try to use devkit-disks. if this fails, then we can fall back to hal
        dk_obj = bus.get_object('org.freedesktop.DeviceKit.Disks', '/org/freedesktop/DeviceKit/Disks')
        dk = dbus.Interface(dk_obj, 'org.freedesktop.DeviceKit.Disks')
        devices = dk.EnumerateDevices()
        for device in devices:
            dev_obj = bus.get_object('org.freedesktop.DeviceKit.Disks', device)
            dev = dbus.Interface(dev_obj, 'org.freedesktop.DBus.Properties')

            label = dev.Get('org.freedesktop.DeviceKit.Disks.Device','id-label')
            fs = dev.Get('org.freedesktop.DeviceKit.Disks.Device','id-type')

            if not up and 'DellUtility' in label:
                up=dev.Get('org.freedesktop.DeviceKit.Disks.Device','device-file')
            elif not rp and ('install' in label or 'OS' in label) and 'vfat' in fs:
                rp=dev.Get('org.freedesktop.DeviceKit.Disks.Device','device-file')
        return (up,rp)

    except dbus.DBusException, e:
        print "%s, DeviceKit-Disks Failed" % str(e)

    try:
        hal_obj = bus.get_object('org.freedesktop.Hal', '/org/freedesktop/Hal/Manager')
        hal = dbus.Interface(hal_obj, 'org.freedesktop.Hal.Manager')
        devices = hal.FindDeviceByCapability('volume')

        for device in devices:
            dev_obj = bus.get_object('org.freedesktop.Hal', device)
            dev = dbus.Interface(dev_obj, 'org.freedesktop.Hal.Device')

            label = dev.GetProperty('volume.label')
            fs = dev.GetProperty('volume.fstype')
            if not up and 'DellUtility' in label:
                up=dev.GetProperty('block.device')
            elif not rp and ('install' in label or 'OS' in label) and 'vfat' in fs:
                rp=dev.GetProperty('block.device')
        return (up,rp)
    except dbus.DBusException, e:
        print "%s, HAL Failed" % str(e)

def find_burners():
    """Checks for what utilities are available to burn with"""
    def which(program):
        import os
        def is_exe(fpath):
            return os.path.exists(fpath) and os.access(fpath, os.X_OK)

        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file

        return None

    def find_command(array):
        for item in array:
            path=which(item)
            if path is not None:
                return [path] + array[item]
        return None

    dvd = find_command(dvd_burners)
    usb = find_command(usb_burners)

    #If we have apps for DVD burning, check hardware
    if dvd:
        found_supported_dvdr = False
        try:
            bus = dbus.SystemBus()
            #first try to use udisks, if this fails, fall back to devkit-disks.
            udisk_obj = bus.get_object('org.freedesktop.UDisks', '/org/freedesktop/UDisks')
            ud = dbus.Interface(udisk_obj, 'org.freedesktop.UDisks')
            devices = ud.EnumerateDevices()
            for device in devices:
                dev_obj = bus.get_object('org.freedesktop.UDisks', device)
                dev = dbus.Interface(dev_obj, 'org.freedesktop.DBus.Properties')

                supported_media = dev.Get('org.freedesktop.UDisks.Device','DriveMediaCompatibility')
                for item in supported_media:
                    if 'optical_dvd_r' in item:
                        found_supported_dvdr = True
                        break
                if found_supported_dvdr:
                    break
            if not found_supported_dvdr:
                dvd = None
            return (dvd,usb)
        except dbus.DBusException, e:
            print "%s, UDisks Failed burner parse" % str(e)
        try:
            #first try to use devkit-disks. if this fails, then, it's OK
            dk_obj = bus.get_object('org.freedesktop.DeviceKit.Disks', '/org/freedesktop/DeviceKit/Disks')
            dk = dbus.Interface(dk_obj, 'org.freedesktop.DeviceKit.Disks')
            devices = dk.EnumerateDevices()
            for device in devices:
                dev_obj = bus.get_object('org.freedesktop.DeviceKit.Disks', device)
                dev = dbus.Interface(dev_obj, 'org.freedesktop.DBus.Properties')

                supported_media = dev.Get('org.freedesktop.DeviceKit.Disks.Device','DriveMediaCompatibility')
                for item in supported_media:
                    if 'optical_dvd_r' in item:
                        found_supported_dvdr = True
                        break
                if found_supported_dvdr:
                    break
            if not found_supported_dvdr:
                dvd = None
        except dbus.DBusException, e:
            print "%s, device kit Failed burner parse" % str(e)

    return (dvd,usb)

def match_system_device(bus, vendor, device):
    '''Attempts to match the vendor and device combination to the system on the specified bus
       Allows the following formats:
       str (eg '1234')
       int (eg 1234)
       base 16 int (eg 0x1234)
       base 16 int in a str (eg '0x1234')
    '''
    def recursive_check_ids(directory, check_vendor, check_device):
        vendor = device = ''
        for root, dirs, files in os.walk(directory, topdown=False):
            for file in files:
                if file == 'vendor' or file == 'idVendor':
                    with open(os.path.join(root,file),'r') as filehandle:
                        vendor = filehandle.readline().strip('\n')
                elif file == 'device' or file == 'idProduct':
                    with open(os.path.join(root,file),'r') as filehandle:
                        device = filehandle.readline().strip('\n')
            if vendor and device:
                if ( int(vendor,16) == int(check_vendor) or vendor.strip('0x') == check_vendor ) and \
                   ( int(device,16) == int(check_device) or device.strip('0x') == check_device ) :
                   return True
            if not files:
                for dir in dirs:
                    if recursive_check_ids(os.path.join(root,dir), check_vendor, check_device):
                        return True
        return False

    if bus != "usb" and bus != "pci":
        return False

    if type(vendor) == str and '0x' in vendor:
        vendor = int(vendor,16)
    elif type(vendor) == int:
        vendor = str(vendor)
    if type(device) == str and '0x' in device:
        device = int(device,16)
    elif type(device) == int:
        device = str(device)

    return recursive_check_ids('/sys/bus/%s/devices' % bus, vendor, device)

def increment_bto_version(version):
    match = re.match(r"(?:(?P<alpha1>\w+\.[a-z]*)(?P<digits>\d+))"
                     r"|(?P<alpha2>\w+(?:\.[a-z]+)?)",
                     version, re.I)

    if match:
        if match.group('digits'):
            version="%s%d" % (match.group('alpha1'),
                              int(match.group('digits'))+1)
        else:
            if '.' in match.group('alpha2'):
                version="%s1" % match.group('alpha2')
            else:
                version="%s.1" % match.group('alpha2')
    else:
        return 'A00'

    return version

def dbus_sync_call_signal_wrapper(dbus_iface, fn, handler_map, *args, **kwargs):
    '''Run a D-BUS method call while receiving signals.

    This function is an Ugly Hack™, since a normal synchronous dbus_iface.fn()
    call does not cause signals to be received until the method returns. Thus
    it calls fn asynchronously and sets up a temporary main loop to receive
    signals and call their handlers; these are assigned in handler_map (signal
    name → signal handler).
    '''
    if not hasattr(dbus_iface, 'connect_to_signal'):
        # not a D-BUS object
        return getattr(dbus_iface, fn)(*args, **kwargs)

    def _h_reply(result=None):
        global _h_reply_result
        _h_reply_result = result
        loop.quit()

    def _h_error(exception=None):
        global _h_exception_exc
        _h_exception_exc = exception
        loop.quit()

    loop = gobject.MainLoop()
    global _h_reply_result, _h_exception_exc
    _h_reply_result = None
    _h_exception_exc = None
    kwargs['reply_handler'] = _h_reply
    kwargs['error_handler'] = _h_error
    kwargs['timeout'] = 86400
    for signame, sighandler in handler_map.iteritems():
        dbus_iface.connect_to_signal(signame, sighandler)
    dbus_iface.get_dbus_method(fn)(*args, **kwargs)
    loop.run()
    if _h_exception_exc:
        raise _h_exception_exc
    return _h_reply_result


##                ##
## Common Classes ##
##                ##

class CreateFailed(dbus.DBusException):
    _dbus_error_name = 'com.dell.RecoveryMedia.CreateFailedException'

class PermissionDeniedByPolicy(dbus.DBusException):
    _dbus_error_name = 'com.dell.RecoveryMedia.PermissionDeniedByPolicy'

class BackendCrashError(SystemError):
    pass
