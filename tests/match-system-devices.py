#!/usr/bin/python
from Dell.recovery_common import match_system_device
import subprocess

pci_call = subprocess.Popen(['lspci', '-n'], stdout=subprocess.PIPE)
pci_output = pci_call.communicate()[0]
for line in pci_output.split('\n'):
    if line:
        vendor = line.split(':')[2].strip()
        product = line.split(':')[3].split()[0]
        print "Trying to match PCI %s:%s."  % (vendor,product)
        print match_system_device('pci','0x' + vendor, '0x' + product)

usb_call = subprocess.Popen(['lsusb'], stdout = subprocess.PIPE)
usb_output = usb_call.communicate()[0]
for line in pci_output.split('\n'):
    if line:
        vendor = line.split(':')[2].strip()
        product = line.split(':')[3].split()[0]
        print "Trying to match USB %s:%s."  % (vendor,product)
        print match_system_device('pci','0x' + vendor, '0x' + product)

#print pci_devices
#print match_system_device('usb','0x0fca','0x8004')
#print match_system_device('usb',0x0fca,0x8004)
#print match_system_device('pci','0x8086','0x2849')
#print match_system_device('pci',0x8086,0x2849)