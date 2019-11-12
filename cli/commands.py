#!/usr/bin/env python
# coding=utf-8


import sys
sys.path.insert(1, "../")

import os
import subprocess
import re


def file_exists(file):
	if not os.path.isfile("./" + file):
		print(file + " does not exist you fucking degenerate")
		return False
	return True


def valid_ip(ip_address):
	pattern = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
	if not pattern.match(ip_address):
		print("invalid ip address you fucking degenerate")
		return False
	return True

def command_send(arguments, options, flags):
	command = "client_main.py"

	file = arguments[0]
	if not file_exists(file):
		return

	ip_address = arguments[1]
	if not valid_ip(ip_address):
		return

	subprocess.call(["python3", command, file, ip_address])


def command_receive(arguments, options, flags):
	command = "server_main.py"

	subprocess.call(['sudo', "python3", command])


def command_exit():
	sys.exit(0)
