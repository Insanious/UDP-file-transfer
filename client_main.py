#!/usr/bin/env python
# coding=utf-8


import sys

from Client import Client
from File_Packager import File_Packager


def extract_arguments():
	if len(sys.argv) != 3: # sys.argv=[python_file(UDPclient.py), file_name, server_ip]
		print("invalid arguments")
		sys.exit(0)

	file_name = sys.argv[1]
	server_ip = sys.argv[2]
	return file_name, server_ip


def main():
	file_name, server_ip = extract_arguments()
	packager = File_Packager(file_name)
	client = Client(server_ip)

	meta_packet, chunks = packager.file_to_chunks()

	client.send_all_chunks(meta_packet, chunks)
	client.close_socket()


main()
