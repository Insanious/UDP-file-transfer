#!/usr/bin/env python

import logging
import argparse
import sys

from client.Client import Client
from utilities.File_Packager import File_Packager


def send_file(filename, server_ip):
	packager = File_Packager(filename)
	client = Client(server_ip)
	meta_packet, chunks = packager.file_to_chunks()
	client.send_all_file_chunks(meta_packet, chunks)
	client.close_socket()


def main():
	parser = argparse.ArgumentParser(description="Send a file to an ip address")
	parser.add_argument("filename", metavar="filename", type=str, help="the file to send")
	parser.add_argument("ip-address", metavar="ip-address", type=str, help="the ip address to send the file to")
	parser.add_argument("-log", metavar="--log_level", type=str, help="the log level")

	args = vars(parser.parse_args())

	filename = args["filename"]
	server_ip = args["ip-address"]

	log_level = args["log"]
	log_level = log_level.upper() if log_level != None else "WARNING"
	logging.basicConfig(level=log_level)

	logger = logging.getLogger(__name__)
	logger.setLevel(log_level)

	send_file(filename, server_ip)


if __name__ == "__main__":
	main()
