#!/usr/bin/env python
# coding=utf-8


import os

from Server import Server
from file_manipulation import create_file_from_packets
from file_manipulation import create_file_from_binary_packets


def main():
	server = Server()
	file_name, packets = server.receive_all_chunks()

	file_name = "copy_" + file_name
	path = "temp"
	file_name = os.path.join(path, file_name)

	if create_file_from_binary_packets(file_name, packets):
		print("Successfully created " + file_name + " from " + str(len(packets)) + " packets!")


main()
